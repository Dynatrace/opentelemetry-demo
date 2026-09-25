import json
from opentelemetry import propagate

def extract_parent(msg, from_sns_payload=False):
    if from_sns_payload:
        try:
            body = json.loads(msg.get("Body", "{}"))
        except json.JSONDecodeError:
            body = {}
        carrier = {key: value["Value"] for key, value in body.get("MessageAttributes", {}).items() if "Value" in value}
    else:
      carrier = {key: value["StringValue"] for key, value in msg.get("MessageAttributes", {}).items() if "StringValue" in value}

    return propagate.extract(carrier)

def request_hook(span, service_name, operation_name, api_params):
    '''
    Request Hook function for OpenTelemetry BotocoreInstrumentor to add metadata
    '''
    if service_name == 's3':
        span.set_attribute('aws.s3.bucket',api_params.get('Bucket','unknown'))
        span.set_attribute('aws.s3.key',api_params.get('Key','unknown'))

    return
