const crypto = require('crypto');
import { AwsCredentialIdentityProvider } from "@smithy/types";
import { AwsClient } from 'aws4fetch'
import { logger } from '../utils/Logger'
const delay = (ms: number): Promise<void> => new Promise(resolve => setTimeout(resolve, ms));

export class Translations {
    private credentials: AwsCredentialIdentityProvider;
    private translationEndpoint: string;

    constructor(credentials: AwsCredentialIdentityProvider, translationEndpointUri: string) {
        if (!translationEndpointUri) {
            throw new Error('Translation endpoint URI is required');
        }
        this.credentials = credentials;
        this.translationEndpoint = translationEndpointUri;
    }

    public async requestTranslation(id: string, fields: [{ name: string, value: string }]): Promise<boolean> {
        let result = true;
        logger.info('Translation Endpoint', this.translationEndpoint);

        // get temporary credentials
        const creds = await this.credentials();
        // create an AWS fetch client
        const awsFetchClient = new AwsClient({ accessKeyId: creds.accessKeyId, secretAccessKey: creds.secretAccessKey, sessionToken: creds.sessionToken, service: 'execute-api' });
        // enumerate the fields to translate and start the translation request
        for (const field of fields) {
            const requestPayload = {
                translation_id: id,
                translation_field: field.name,
                message: field.value,
                sourceLanguage: "en",
                destinationLanguages: ["es", "de"]
            };
            const body = JSON.stringify(requestPayload);
            logger.info('Requesting translation', body);

            // send the translation request
            const fetchResponse = await awsFetchClient.fetch(this.translationEndpoint, {
                body: body
            });
            // try {
            if (fetchResponse.ok) {
                const data = await fetchResponse.json();
                logger.info('Successfully requested translation', data);
            }
            else {
                logger.info('Failure requesting translation');
                const contentType = fetchResponse.headers.get('Content-Type')
                if (contentType && contentType.includes('application/json'))
                    console.dir(await fetchResponse.json(), { depth: null });
                else
                    logger.info(await fetchResponse.text());

                // Custom message for failed HTTP codes
                if (fetchResponse.status === 404) throw new Error('404, Not found');
                if (fetchResponse.status === 500) throw new Error('500, internal server error');
                // For any other server error
                throw new Error(fetchResponse.status.toString());
            }
            // } catch (error) {
            //     result = false; // one or more translation requests failed
            //     logger.error('Failure executing Fetch', error);
            // }
            await delay(1000); // delay 1 second between translation requests
        }
        return result;
    }
}