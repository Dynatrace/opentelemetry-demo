import dotenv from 'dotenv';
dotenv.config();

const env = process.env.NODE_ENV || 'development';
const translationEndpointUri = process.env.TRANSLATIONS_ENDPOINT_URI || '';
const dbHost = process.env.DB_HOST || '';
const dbName = process.env.DB_NAME || 'products';
const dbUsername = process.env.DB_USER || 'product_user';
const dbAdminUsername = process.env.DB_ADMIN_USER || 'product_admin';
const dbAdminPassword = process.env.DB_ADMIN_PASSWORD || '';
const dbCAPath = process.env.DB_CA_CERTIFICATE || './certs/us-east-1-bundle.pem';
import express, { Application, Request, Response, NextFunction } from 'express';
import { pinoHttp } from "pino-http";
import serverless from 'serverless-http';
import * as fs from 'fs';
import { AwsCredentialIdentityProvider } from "@smithy/types";
import { fromIni } from "@aws-sdk/credential-providers";
import { defaultProvider } from '@aws-sdk/credential-provider-node';
import readline from "readline";
import cors from 'cors';
import SubscriptionRoutes from './routes/SubscriptionRoutes';
import { Database } from './services/Database';
import { Translations } from './services/Translations';
import ProductTranslationRoutes from './routes/ProductTranslationRoutes';
import Auth from './middleware/Auth';
import { logger } from './utils/Logger'
import ProductCategoryV2Routes from './routes/ProductV2CategoryRoutes';
import ProductRoutes from './routes/ProductRoutes';
import ProductV2Routes from './routes/ProductV2Routes';

class Server {
  private app: Application;
  private handler: any;
  private aws_credentials: AwsCredentialIdentityProvider;
  private auth: Auth;
  private port: number;
  private database: Database;
  private translations: Translations;
  private jsonSettings = { limit: '50mb', type: 'application/json', strict: false };


  constructor() {
    this.app = express();
    this.handler = null;
    this.port = process.env.PORT ? Number(process.env.PORT) : 3000;
    this.aws_credentials = this.getAwsCredentials();
    this.auth = new Auth();
    this.translations = new Translations(this.aws_credentials, translationEndpointUri)
    // Get the contents of cert file
    logger.info(`Using CA certificate from ${dbCAPath}`);
    const dbCA = fs.readFileSync(dbCAPath, { encoding: "utf8" });
    logger.info(`Initializing database connection (host: ${dbHost}, dbName: ${dbName})`);
    this.database = new Database(this.aws_credentials, dbHost, dbName, dbUsername, dbAdminUsername, dbAdminPassword, dbCA);
    this.configureApp();
  }

  private prompt(question: string): Promise<string> {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });

    return new Promise((resolve) =>
      rl.question(question, (ans) => {
        rl.close();
        resolve(ans);
      })
    );
  }

  private getAwsCredentials(prod = process.env.PROD): AwsCredentialIdentityProvider {
    if (prod) {
      logger.info('Using default AWS Auth provider');
      return defaultProvider();
    }
    // This assumes that you've set-up your ~/.aws/config and credentials!
    logger.info('Using local shared AWS credentials');
    return fromIni({
      mfaCodeProvider: async (mfaSerial: string): Promise<string> => {
        return await this.prompt(`Type the mfa token for the following account: ${mfaSerial}\n`);
      }
    });
  }

  private configureApp() {
    // all environments
    this.app.set('port', this.port);

    // Setup middleware
    this.app.use(cors());

    // Log with pino
    this.app.use(pinoHttp({ logger: logger }));

    // health probe
    this.app.get('/health', (req: Request, res: Response, next: NextFunction) => {
      return res.send('OK');
    });

    // Register Routes
    this.app.use('/db/v2/product', this.auth.isAuthorized, express.json(this.jsonSettings), new ProductV2Routes(this.database, this.translations).router)
    this.app.use('/db/v2/product-category', this.auth.isAuthorized, express.json(this.jsonSettings), new ProductCategoryV2Routes(this.database).router)
    this.app.use('/db/product', this.auth.isAuthorized, express.json(this.jsonSettings), new ProductRoutes(this.database, this.translations).router)
    this.app.use('/db/product-translation', this.auth.isAuthorized, express.json(this.jsonSettings), new ProductTranslationRoutes(this.database).router)
    this.app.use('/subscription', new SubscriptionRoutes(this.aws_credentials, this.database).router)
  }

  public async startStandalone() {
    const start = Date.now();
    // Boot the database
    await this.database.init();
    // Sync database schema, re-create the database if required
    await this.database.sync(true);
    // boot the express server on the required port
    this.app.listen(this.port, () => {
      const duration = Date.now() - start;
      logger.info(`⚡️[server]: Server is running at http://localhost:${this.port}`)
    })
  }

  public async serverlessHandler(event: object, context: object): Promise<object | undefined> {
    if (!this.app)
      throw new Error('Express application not initialized!');

    // Boot the database
    await this.database.init();

    if (!this.handler) {
      // Sync database schema
      await this.database.sync(true);
      // cache the serverless handler
      this.handler = serverless(this.app);
      logger.info(`⚡️[serverless]: Serverless handler is cached`)
    }
    // return cached handler
    return this.handler(event, context);
  }
}

// Boot our server application
const server = new Server();
if (env !== "production") {
  server.startStandalone();
}

// export the handler for serverless deployment
module.exports.handler = async (event: object, context: object) => {
  // return the serverless handler
  return await server.serverlessHandler(event, context);
}
