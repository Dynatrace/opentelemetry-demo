const { registerInstrumentations } = require("@opentelemetry/instrumentation");
const { WinstonInstrumentation } = require('@opentelemetry/instrumentation-winston')
const { AwsInstrumentation } = require("@opentelemetry/instrumentation-aws-sdk");

registerInstrumentations({
    instrumentations: [
        new AwsInstrumentation({
            suppressInternalInstrumentation: true,
            sqsExtractContextPropagationFromPayload: true,
            preRequestHook: (span,request) => {
                if (span.attributes['rpc.service'] === "S3"){
                    span.setAttribute('aws.s3.bucket', request.request.commandInput.Bucket);
                    span.setAttribute('aws.s3.key', request.request.commandInput.Key)
                }
            }
        }),
        new WinstonInstrumentation()
    ],
});