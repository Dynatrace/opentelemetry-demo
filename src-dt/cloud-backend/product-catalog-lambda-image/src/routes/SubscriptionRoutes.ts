import express, { NextFunction, Request, Response, Router } from 'express';
import { GetObjectCommand, S3Client } from '@aws-sdk/client-s3';
import { AwsCredentialIdentityProvider } from "@smithy/types";
import * as AWSXRay from 'aws-xray-sdk';
import zlib from 'zlib';
import util from 'util';
import { Notification } from 'interfaces/Notification';
import { SubscriptionConfirmation } from 'interfaces/SubscriptionConfirmation';
const zlibGunzip = util.promisify(zlib.gunzip);
import { Database } from 'services/Database';

export default class SubscriptionRoutes {
  public router: Router;
  private s3_client: S3Client;
  private database: Database;

  constructor(aws_credentials: AwsCredentialIdentityProvider, database: Database) {
    this.router = express.Router();
    this.database = database;
    this.s3_client = this.getAwsSdkv3Client(new S3Client({ credentials: aws_credentials }));
    this.registerRoutes();
  }

  protected registerRoutes(): void {
    // Setup express Routes
    this.router.post('/', this.handleSubscription.bind(this));
  }

  private async handleSubscription(req: Request, res: Response, next: NextFunction) {
    req.log.info('POST /subscription');

    if (!req.body) {
      req.log.warn('No body in request');
      return res.status(400).send('No body in request');
    }

    let body = req.body;

    // Is the content gzipped?
    if (req.headers['content-encoding'] == 'gzip') {
      req.log.info("Attempting to decompress GZIP data")
      body = await zlibGunzip(req.body);
    }

    req.log.info('REQUEST BODY:', body)

    try {
      if (req.header('x-amz-sns-message-type') === 'SubscriptionConfirmation') {
        const payload = JSON.parse(body) as SubscriptionConfirmation;
        try {
          req.log.info('Confirming subscription at', payload.SubscribeURL);
          const fetchResponse = await fetch(payload.SubscribeURL, { method: 'GET' });

          if (fetchResponse.status === 200) {
            const data = await fetchResponse.text();
            req.log.info('Successfully confirmed sns subscription', data);
          }
          else
            req.log.error('Failure confirming sns subscription');

          return res.send('OK');
        }
        catch (err) {
          req.log.error(err);
        }
      } else if (req.header('x-amz-sns-message-type') === 'Notification') {
        req.log.info('Notification received');
        //   {
        //         "Type": "Notification",
        //         "MessageId": "8ab7eae8-af56-5124-92ae-b5af4d2f3966",
        //         "TopicArn": "arn:aws:sns:us-east-1:512220559759:oteldemocloudnative-DataProcessingFanOutTopic-OZ9wowKURjLB",
        //         "Message": "{\"request_id\": \"a9368fc7-500b-4e67-8779-b78e35cd50ea\", \"bucket\": \"oteldemocloudnative-dataprocessings3bucket-gv9hkywljyvt\", \"key\": \"a9368fc7-500b-4e67-8779-b78e35cd50ea.json\"}",
        //         "Timestamp": "2024-08-27T14:18:33.647Z",
        //         "SignatureVersion": "1",
        //         "Signature": "P8QLiAWI2Av5BFsW2fsiM4F2O3CbrxdgwwBlD8gANtPy7jlJDzlQDcMLxT5z8GPQlggVsqq6egmxpGqJXkQFMHghMrpMQ7m5xp9WdGfNA9KWEtiTNJhItWZ83H9rRU3vSNE/sT0/9fbGAYMwekPCQx1aaBx4H45W1V+ScCctZNiv++IgJ47R147f2IVC/VD0czn6a1VTLgv1ZL+aE/dmzRFypMvKYA2hVyiqUyjkfx4pZVsFVZHgpiQJURwePHJY9RVJuSgQjZ6BbzaxgH1f91ZPYFjkHLOGeqehKyFARKA+qQY9bPksmfE9YvT+sCROCkEvMDPIVMPPrHgNO4pyUA==",
        //         "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-60eadc530605d63b8e62a523676ef735.pem",
        //         "UnsubscribeURL": "https://sns.us-east-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:us-east-1:512220559759:oteldemocloudnative-DataProcessingFanOutTopic-OZ9wowKURjLB:ca186f99-8f28-4c48-b2b2-be9e1fd70844"
        //  }
        const payload = JSON.parse(req.body) as Notification;
        const message = JSON.parse(payload.Message);
        const command = new GetObjectCommand({
          Bucket: message.bucket,
          Key: message.key,
        });
        try {
          req.log.info('Retrieving object from S3', message.bucket, message.key);
          const commandResponse = await this.s3_client.send(command);
          // The Body object also has 'transformToByteArray' and 'transformToWebStream' methods.
          if (!commandResponse.Body) {
            throw new Error('No body in response');
          }
          // {
          //   "request_id": "c59d696b-0fd2-4efd-af48-f837dcb48b77",
          //   "requestTimestamp": "2024-08-27T15:08:47.665Z",
          //   "message": "hello how are you?",
          //   "sourceLanguage": "en",
          //   "destinationLanguages": [
          //     "es",
          //     "fr"
          //   ],
          //   "translations": [
          //     {
          //       "language": "es",
          //       "message": "hola, ¿cómo estás?"
          //     },
          //     {
          //       "language": "fr",
          //       "message": "Bonjour, comment allez-vous ?"
          //     }
          //   ],
          //   "errors": [

          //   ],
          //   "result": "OK",
          //   "processedAt": "2024-08-27T15:08:49Z.107203",
          //   "data_processing_message_id": "d27122d3-4d32-43c8-b401-6782470fe380"
          // }
          const str = await commandResponse.Body.transformToString();
          req.log.debug('Got object from S3', message.bucket, message.key);
          const translation = JSON.parse(str);
          if (translation.translation_id &&
            translation.result == "OK") {
            req.log.info('Translation', translation);
            // enumerate the translations and insert into DB
            for (const t of translation.translations) {
              // We need to upsert the translation
              req.log.info('Received translation', t);
              const existingTranslation = await this.database.ProductTranslation.findOne({ where: { language: t.language, product_id: translation.translation_id } });
              if (existingTranslation) {
                // If the translation exists, update its data
                req.log.info('Found existing translation', existingTranslation);
                if (await this.database.ProductTranslation.update({
                  description: t.message
                }, {
                  where:
                  {
                    id: existingTranslation.id
                  },
                  returning: true
                }))
                  req.log.info('Updated existing translation');
                else
                  req.log.warn('Failed to update existing translation');
              } else {
                req.log.info('Storing new translation');
                // If the user does not exist, create a new user with the provided data
                if (await this.database.ProductTranslation.create({
                  language: t.language,
                  description: t.message,
                  product_id: translation.translation_id
                },
                  {
                    returning: true
                  }))
                  req.log.info('Stored new translation');
                else
                  req.log.warn('Failed to store new translation');
              }
            }
          }
          // Return Success
          req.log.info('Successfully processed translations');
          return res.send('OK');
        } catch (err) {
          req.log.error(err);
        }
      } else if (req.header('x-amz-sns-message-type')) {
        req.log.error(`Invalid message type ${req.header('x-amz-sns-message-type')}`);
        return res.status(400).send();
      } else {
        req.log.error(`Invalid message`);
        return res.status(400).send();
      }
    } catch (err) {
      req.log.error(err);
    }
    return res.status(500).send();
  }

  private getAwsSdkv3Client(client: S3Client): S3Client {
    if (process.env.INSTRUMENT_WITH_XRAY == 'true') {
      return AWSXRay.captureAWSv3Client(client);
    } else {
      return client;
    }
  }
}
