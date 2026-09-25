const instrumentation = require('./instrument.js')
const winston = require('winston');
const { SQSClient, SendMessageCommand } = require("@aws-sdk/client-sqs");
const { DynamoDBClient, PutItemCommand } = require("@aws-sdk/client-dynamodb");
const { marshall } = require("@aws-sdk/util-dynamodb");
const { LambdaClient, InvokeCommand } = require("@aws-sdk/client-lambda");
const Validator = require('jsonschema').Validator;

const logger = winston.createLogger({
    level: process.env.LOG_LEVEL.toLowerCase() || 'info',
    format: winston.format.json(),
    defaultMeta: { service: 'raw-data-persistence-service' },
    transports: [
        new winston.transports.Console()
    ]
});

function getAwsSdkv3Client(client) {
    if ( process.env.INSTRUMENT_WITH_XRAY == 'true' ) {
        const AWSXray = require('aws-xray-sdk');
        return AWSXray.captureAWSv3Client(client);
    } else {
        return client;
    }
}

const sqs = getAwsSdkv3Client(new SQSClient({}));
const ddb = getAwsSdkv3Client(new DynamoDBClient({}));
const lambda = getAwsSdkv3Client(new LambdaClient({}));

function request_is_valid(request) {
    let v = new Validator();

    let requestSchema = {
        'id': '/requestSchema',
        'type': 'object',
        'properties': {
            'message': {'type':'string'},
            'sourceLanguage': {'type':'string'},
            'destinationLanguages': {
                'type': ' array',
                'items': {'type':'string'}
            }
        },
        'required': ['message', 'sourceLanguage', 'destinationLanguages']
    };

    return v.validate(request,requestSchema).valid;
}


function send_http_response(type, body='{\"message\": \"OK\"}') {

    response = {};

    if (type == 'OK') {
        response = {
            'statusCode': 200,
            'headers':{
                'Content-Type': 'application/json'
            },
            'body': body
        };
    }
    else if (type == 'SERVER_ERROR') {
        response = {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': '{\"message\": \"Error processing request\"}'
        };
    }
    else if (type == 'METHOD_NOT_ALLOWED') {
        response = {
            'statusCode': 405,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': '{\"message\": \"HTTP Method not allowed\"}'
        };
    }
    else if (type == 'BAD_REQUEST') {
        response = {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': '{\"message\": \"Request is invalid\"}'
        };
    }
    else {
        response= {
            'statusCode': 502,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': '{\"message\": \"Unknown error\"}'
        };
    }

    return response;
}

exports.handler = async (event,context) => {

    logger.defaultMeta = {
        lambdaRequestId: context.awsRequestId,
        requestId: event.requestContext.requestId
    };
    logger.debug(event);

    try {
        
        if ((event.httpMethod == 'GET') && (event.path == '/GetUsageReport')) {
            logger.info('Processing usage report request...');
            const response = await lambda.send(new InvokeCommand({
                FunctionName: process.env.REPORTING_FUNCTION_NAME,
                Payload: JSON.stringify({
                    'Operation': 'get-report'
                })
            }));

            logger.debug(response)

            const resp_str_payload = Buffer.from(response.Payload).toString(); 

            var resp_payload = {
                'message': 'OK',
                'content': JSON.parse(resp_str_payload)
            }
            
            return send_http_response('OK',JSON.stringify(resp_payload))

        } else if (event.httpMethod != 'POST') {
            return send_http_response('METHOD_NOT_ALLOWED');
        }

        var jBody = JSON.parse(event.body);

        if (!request_is_valid(jBody)) {
            return send_http_response('BAD_REQUEST');
        }

        const timestamp = new Date();

        var item = {
            request_id: event.requestContext.requestId,
            requestTimestamp: `${timestamp.toISOString()}`,
            ...jBody
        };

        await ddb.send(new PutItemCommand({
                TableName: process.env.TABLE_NAME,
                Item: marshall(item)
            })
        );

        logger.info('Persisted request in DynamoDB');

        await sqs.send(new SendMessageCommand({
                QueueUrl: process.env.QUEUE_URL,
                MessageBody: JSON.stringify(item)
            })
        );

        logger.info('Sent request to SQS for downstream processing');

    } catch (error) {

        logger.error(error.stack);
        return send_http_response('SERVER_ERROR');

    }

    return send_http_response('OK');

}