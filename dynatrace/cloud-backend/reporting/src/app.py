# import instrumentation
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
###
import logging
import os
import json
from redis.cluster import RedisCluster as Redis
import boto3

# If env var is set, instrument code with X-Ray
if os.environ.get('INSTRUMENT_WITH_XRAY','') == 'true':
    from aws_xray_sdk.core import xray_recorder
    from aws_xray_sdk.core import patch_all
    patch_all()

# Instrument Boto3 and Redis Client
def request_hook(span, service_name, operation_name, api_params):
    '''
    Request Hook function for OpenTelemetry BotocoreInstrumentor to add metadata
    '''
    if service_name == 's3':
        span.set_attribute('aws.s3.bucket',api_params.get('Bucket','unknown'))
        span.set_attribute('aws.s3.key',api_params.get('Key','unknown'))

    return

BotocoreInstrumentor().instrument(request_hook=request_hook)
RedisInstrumentor().instrument()

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL',logging.INFO))

PRICE_PER_CHARACTER=15/1000000

# initialize redis connection
r = Redis(
    host=os.environ.get('CACHE_ENDPOINT'),
    port=6379,
    charset='utf-8',
    decode_responses=True,
    ssl=True
)

s3_client = boto3.client('s3')

def download_message_from_s3(body):
    obj = json.loads(
        s3_client.get_object(
            Bucket=body['bucket'],
            Key=body['key']
        )['Body'].read()
    )

    return obj

def process_sqs_message(event):

    batchItemFailures = { 'batchItemFailures': [] }

    for i,record in enumerate(event['Records']):
        try:
            message_id = record['messageId']
            logger.info("Processing message [%s] - %s", str(i), message_id)
            
            body = json.loads(json.loads(record['body'])['Message'])
            
            # download full object from S3
            full_obj = download_message_from_s3(body)

            report = {
                "word_count": len(full_obj['message'].split()),
                "character_count": len(full_obj['message']),
                "num_of_translations": len(full_obj['translations'])
            }

            report['translation_cost'] = PRICE_PER_CHARACTER * report['character_count']

            logger.info("Report for request %s - %s",full_obj['request_id'],json.dumps(report))

            p = r.pipeline()
            p.incrby("TOTAL_WORD_COUNT",report['word_count'])
            p.incrby("TOTAL_CHAR_COUNT",report['character_count'])
            p.incrby("TOTAL_PROCESSED_TRANSLATIONS",report['num_of_translations'])
            p.incrbyfloat("TOTAL_TRANSLATION_COSTS",report['translation_cost'])
            p.hmset(full_obj['request_id'],report)

            p.execute()

            logger.info("Persisted record in redis - %s", full_obj['request_id'])

        except Exception:
            logger.exception("There was an error processing the message")
            batchItemFailures['batchItemFailures'].append({
                'itemIdentifier': message_id
            })

    return batchItemFailures

def process_sync_request(event):

    report = {}

    if event.get('Operation','') == 'get-report':
        keys = ['TOTAL_WORD_COUNT','TOTAL_CHAR_COUNT', 'TOTAL_PROCESSED_TRANSLATIONS',
                    'TOTAL_TRANSLATION_COSTS' ]

        p = r.pipeline()

        for key in keys:
            p.get(key)

        values = p.execute()

        logger.info("Reading keys from Redis: %s", str(values))

        report = dict(zip(keys,values))

    return report


def lambda_handler(event, context):

    logger.debug(json.dumps(event))

    if event.get('Records', False):
        return process_sqs_message(event)
    elif event.get('Operation'):
        return process_sync_request(event)
