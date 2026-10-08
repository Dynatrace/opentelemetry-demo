const { trace, SpanKind, ROOT_CONTEXT, propagation, context } = require('@opentelemetry/api');
const winston = require("winston");
const { ReceiveMessageCommand, DeleteMessageCommand, SQSClient } = require("@aws-sdk/client-sqs"); 
const { GetObjectCommand, S3Client } = require("@aws-sdk/client-s3")
const { DynamoDB } = require("@aws-sdk/client-dynamodb")
const { marshall } = require("@aws-sdk/util-dynamodb");
const { Span } = require('@opentelemetry/sdk-trace-base');

const tracer = trace.getTracer('processed-data-persistence');

const logger = winston.createLogger({
    level: process.env.LOG_LEVEL.toLowerCase() || 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.json()
    ),
    transports: [
        new winston.transports.Console()
    ]
});

const queue = process.env.QUEUE_URL;
const table = process.env.TABLE_NAME;
const queue_name = queue.split("/").pop()

const sqsClient = new SQSClient({});
const s3Client = new S3Client({});
const ddbClient = new DynamoDB({});

var keepRunning = true;

function gracefulShutdown() {
    logger.info("SIGTERM received. Initiating graceful shutdown...");
    keepRunning = false;
}

async function getFullMessageFromS3(bucket,key) {
    const command = new GetObjectCommand({
        Bucket: bucket,
        Key: key
    });
    const response = await s3Client.send(command);

    const str = await response.Body.transformToString('utf-8');
    return JSON.parse(str);
}

async function processMessage(message) {
    
    await tracer.startActiveSpan(`${queue_name} process`, { kind: SpanKind.CONSUMER }, async (span) => {
        try {
            logger.debug(`SQS Message: ${JSON.stringify(message)}`);

            // Add Span Attributes
            span.setAttribute('messaging.message.id',message.MessageId);
            span.setAttribute('messaging.system','aws.sqs');
            span.setAttribute('messaging.operation','process');
            span.setAttribute('messaging.url', queue);
            
            // Unwrap nested message from SNS 
            const jMessage = JSON.parse(JSON.parse(message.Body).Message);
            logger.info(`Processing request ${jMessage.request_id}`);

            // Add TopicArn to span attributes
            span.setAttribute('messaging.destination.name', JSON.parse(message.Body).TopicArn);

            // Get full message from S3
            bucket = jMessage.bucket;
            key = jMessage.key;
            logger.debug(`Getting full message from s3://${bucket}/${key}`);
            const fullMessage = await getFullMessageFromS3(bucket,key);

            const timestamp = new Date()
            fullMessage.persistedOn = `${timestamp.toISOString()}`

            await ddbClient.putItem({
                TableName: table,
                Item: marshall(fullMessage)
            });

            logger.info('Persisted translation in DynamoDB');

            // delete message
            const deleteMessageCmd = new DeleteMessageCommand({
                QueueUrl: queue,
                ReceiptHandle: message.ReceiptHandle
            });

            sqsClient.send(deleteMessageCmd);
            logger.info(`Deleted message from SQS: ${jMessage.request_id}`);
            return(true)
        } catch (e) {
            logger.error(e);
            return(false)
        } finally {
            span.end();
        }
    });
} 

function extractContextFromMessage(msg, fromSnsPayload=false) {
    let valueKey = "StringValue"
    if (fromSnsPayload) {
        valueKey = "Value";
        try {
            msg = JSON.parse(msg.Body)
        } catch {
            msg = {}
        }
    }
    const carrier = {};
    Object.keys(msg.MessageAttributes || {}).forEach((attrKey) => {
        carrier[attrKey] = msg.MessageAttributes[attrKey]?.[valueKey];
    });

    return propagation.extract(ROOT_CONTEXT, carrier)
}

async function main() {

    process.on('SIGTERM', gracefulShutdown);

    logger.info(`Starting processed-data-persistence queue processor. Queue: ${queue} Table: ${table}`);

    const receiveMessageCmd = new ReceiveMessageCommand({
        AttributeNames: ["All"],
        MaxNumberOfMessages: 10,
        QueueUrl: queue,
        WaitTimeSeconds: 20
    });

    // process sqs messages
    while (keepRunning) {
        logger.debug("Polling SQS...");
        const response = await sqsClient.send(receiveMessageCmd);
        logger.debug(response);

        // if no messages, then keeep polling
        if (response.Messages == null) {
            response.Messages = [];
        }
        for (let message of response.Messages) {
            
            const ctx = extractContextFromMessage(message,true);
            await context.with(ctx, async () => {
                processMessage(message)
            });
        };

        // if SIGTERM, stop processing messages
        if (keepRunning==false) {
            break;
        }

    }
}

if (require.main === module) {
    main();
}