const {
    SQSClient,
    ReceiveMessageCommand,
    Message,
    DeleteMessageCommand,
} = require("@aws-sdk/client-sqs")
const { DynamoDBClient, PutItemCommand } = require("@aws-sdk/client-dynamodb")
const winston = require("winston")

require('json-rules-engine-simplified');

/**
 * @typedef Order
 * @type {object}
 * @property {string} order_id
 * @property {string} customer_id
 */

const logger = winston.createLogger({
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.json()
    ),
    transports: [new winston.transports.Console()],
})

/**
 *
 * @param {string} name
 * @returns {string}
 */
function requireEnv(name) {
    const value = process.env[name]
    if (value === undefined || value === "") {
        throw Error(`The env var [${name}] is missing`)
    }
    return value
}

/**
 *
 * @param {SQSClient} client
 * @param {string} queueUrl
 * @returns {Promise<Message[]>}
 */
async function getMessages(client, queueUrl) {
    const response = await client.send(
        new ReceiveMessageCommand({
            QueueUrl: queueUrl,
            MaxNumberOfMessages: 10, // max allowed messages
            WaitTimeSeconds: 20, // max allowed timeout
        })
    )

    return response?.Messages ?? []
}

/**
 *
 * @param {Message} message
 * @param {SQSClient} sqsClient
 * @param {DynamoDBClient} dbClient
 * @param {string} tableName
 * @param {string} queueUrl
 * @returns {Promise}
 */
async function processMessage(
    message,
    sqsClient,
    dbClient,
    tableName,
    queueUrl
) {
    const order = JSON.parse(message.Body)
    logger.info(
        `Processing order with id [${order.order_id}] for customer [${order.customer_id}]`
    )
    try {
        await dbClient.send(
            new PutItemCommand({
                TableName: tableName,
                Item: {
                    order_id: { S: `${order.order_id}` },
                    customer_id: { S: `${order.customer_id}` },
                    // since there's nothing removing the orders from the DB
                    // and we don't want it to grow over time
                    // we use the TTL mechanism in DynamoDB to delete the items
                    expire_at: { N: `${Math.round(Date.now() / 1_000)}` },
                },
            })
        )
    } catch (e) {
        logger.error(`Error persisting order in db: ${e}`)
        return
    }
    try {
        await sqsClient.send(
            new DeleteMessageCommand({
                QueueUrl: queueUrl,
                ReceiptHandle: message.ReceiptHandle,
            })
        )
    } catch (e) {
        logger.error(`Error marking message as completed: ${e}`)
        return
    }
}

async function main() {
    logger.info("Setting up env vars")

    const queueUrl = requireEnv("QUEUE_URL")
    const dynamoDbTable = requireEnv("DYNAMODB_TABLE")
    const awsRegion = requireEnv("AWS_REGION")

    logger.info("Creating clients")

    const sqsClient = new SQSClient({ region: awsRegion })
    const dbClient = new DynamoDBClient({ region: awsRegion })

    logger.info("Start processing messages")
    while (true) {
        logger.info("Polling SQS for messages")
        const messages = await getMessages(sqsClient, queueUrl)

        if (messages.length === 0) {
            logger.info("No messages to process")
            continue
        }

        logger.info(`Processing [${messages.length}] messages`)
        await Promise.allSettled(
            messages.map((m) =>
                processMessage(m, sqsClient, dbClient, dynamoDbTable, queueUrl)
            )
        )
    }
}

main()
