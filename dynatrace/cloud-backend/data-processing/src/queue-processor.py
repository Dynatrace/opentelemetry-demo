from instrumentation_helpers import extract_parent, request_hook
from opentelemetry import trace
from opentelemetry.semconv.trace import SpanAttributes, MessagingOperationValues
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
from opentelemetry.instrumentation.boto3sqs import Boto3SQSInstrumentor

trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter()
span_processor = BatchSpanProcessor(otlp_exporter)

trace.get_tracer_provider().add_span_processor(span_processor)

import os
import signal
import boto3
from botocore.exceptions import ClientError
import json
import logging
from pythonjsonlogger import jsonlogger
from datetime import datetime

def dt_log(self, record):
    if (not self.disabled) and self.filter(record):
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            trace_id = "{0:032X}".format(ctx.trace_id)
            span_id = "{0:016X}".format(ctx.span_id)
            record.msg = f"[!dt dt.trace_id={trace_id},dt.span_id={span_id}] - {record.msg}"
    self.callHandlers(record)

run = True

# Configure Logger
logging.Logger.handle = dt_log
logger = logging.getLogger(__name__)
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s '
                                     '- %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(level=os.environ.get('LOG_LEVEL',logging.INFO))

logger.info("Starting queue-processor.py...")

# Get metadata
queue_url = os.environ.get('QUEUE_URL')
queue_name = queue_url.split('/')[-1]
topic = os.environ.get('TOPIC_NAME')
bucket = os.environ.get('BUCKET_NAME')

# Instrument Boto3 and SQS Client
BotocoreInstrumentor().instrument(request_hook=request_hook)
Boto3SQSInstrumentor().instrument()

# boto3 clients
sqs_client = boto3.client('sqs')
sns_client = boto3.client('sns')
s3_client = boto3.client('s3')
translate_client = boto3.client('translate')

# list of available language codes for translation
available_languages = [ l['LanguageCode'] for l in translate_client.list_languages().get('Languages') ]
logger.info('Pulled available translation lenguages')

# gracefully terminate processing
def terminate(signal,frame):
    global run
    logger.warning("Received SIG %s. Starting gracefull shutdown...",signal)
    run = False

def translate_message(message):
    '''
    Gets a message in JSON format, invokes Amazon Translate to process translations into
    the provided list of languages
    {
        "message": "text to translate",
        "sourceLanguage: "en",
        "destinationLanguages": ["es", "fr" ]
    }
    '''

    processed_msg = message.copy()
    processed_msg.update({
            "translations": [],
            "errors": [],
            "result": "NOT_PROCESSED"
        }
    )

    if message.get('sourceLanguage','') in available_languages:
        for dest_lang in message.get('destinationLanguages',[]):
            if dest_lang in available_languages:
                translated_text = translate_client.translate_text(
                    Text=message.get('message'),
                    SourceLanguageCode=message.get('sourceLanguage'),
                    TargetLanguageCode=dest_lang
                )
                translation = {
                            "language": dest_lang,
                            "message": translated_text.get('TranslatedText'),
                        }

                processed_msg['translations'].append(translation)
                processed_msg['result']="OK"
            else:
                logger.error("Destination language %s not available",dest_lang)
                processed_msg['errors'].append(dest_lang)
                processed_msg['result']="WITH_ERRORS"
    else:
        logger.error("Source Language is not available")
        processed_msg["result"]="UNAVAILABLE_SOURCE_LANGUAGE"

    processed_msg["processedAt"] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ.%f')

    return processed_msg

def process_message(q_message):
    '''
    Processes an SQS message, translating  its content and storing it in S3.
    Notifies SNS once completed
    '''
    success = False

    try:
        logger.info('Processing message %s',q_message['MessageId'])
        logger.debug('SQS Messqge: %s',json.dumps(q_message))
        j_message = json.loads(q_message['Body'])

        processed_msg = translate_message(j_message)
        processed_msg['data_processing_message_id'] = q_message['MessageId']

        logger.info(processed_msg)

        s3_key = f'{processed_msg["request_id"]}.json'

        s3_client.put_object(
            Bucket=bucket,
            Key= s3_key,
            Body=json.dumps(processed_msg,ensure_ascii=False).encode('utf-8')
        )

        logger.info('%s - Persisted translation on S3',processed_msg["request_id"])

        sns_client.publish(
            TopicArn=topic,
            Message=json.dumps({
                'request_id': processed_msg['request_id'],
                'bucket': bucket,
                'key': s3_key
            })
        )

        logger.info('%s - Notified downstream',processed_msg["request_id"])

        sqs_client.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=q_message.get('ReceiptHandle')
        )

        logger.info('%s - pushed notification to SNS', processed_msg["request_id"])
        
        success = True

    except ClientError:
        logger.exception("Can't process request %s",processed_msg["request_id"])

    return success

def main():

    signal.signal(signal.SIGTERM, terminate)

    logger.info("Starting data-processing-service - Queue: %s - Topic: %s - Bucket: %s",
                    queue_url,topic,bucket)

    while run:

        logger.debug("Polling SQS Queue: %s", queue_url)

        queue_response = sqs_client.receive_message(
            QueueUrl=queue_url,
            AttributeNames=['All'],
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20
        )

        for q_message in queue_response.get('Messages',[]):
            parent_ctx = extract_parent(q_message)
            with tracer.start_as_current_span(f"{queue_name} process",
                context= parent_ctx,
                kind= trace.SpanKind.CONSUMER,
                attributes={
                    SpanAttributes.MESSAGING_MESSAGE_ID: q_message['MessageId'],
                    SpanAttributes.MESSAGING_URL: queue_url,
                    SpanAttributes.MESSAGING_SYSTEM: 'aws.sqs',
                    SpanAttributes.MESSAGING_OPERATION: MessagingOperationValues.PROCESS.value
                }):
                process_message(q_message)

            # If SIGTERM, stop processing messages
            if not run:
                break

if __name__ == '__main__':
    main()
