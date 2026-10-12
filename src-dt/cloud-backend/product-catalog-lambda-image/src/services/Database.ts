import { DataTypes, Sequelize } from "sequelize";
import { Client } from "pg";
import { Signer } from "@aws-sdk/rds-signer";
import { AwsCredentialIdentityProvider } from "@smithy/types";
import { logger } from '../utils/Logger'

export class Database {
    private credentials: AwsCredentialIdentityProvider;
    private dbHost: string;
    private dbName: string;
    private dbUsername: string;
    private dbAdminUsername: string;
    private dbAdminPassword: string;
    private dbCA: string;
    private sequelize: Sequelize | null = null;
    public Product: any;
    public ProductTranslation: any;
    public ProductCategory: any;
    public ProductState: any;

    constructor(credentials: AwsCredentialIdentityProvider, dbHost: string, dbName: string, dbUsername: string, dbAdminUsername: string, dbAdminPassword: string, dbCA: string) {
        this.credentials = credentials;
        this.dbHost = dbHost;
        this.dbName = dbName;
        this.dbUsername = dbUsername;
        this.dbAdminUsername = dbAdminUsername;
        this.dbAdminPassword = dbAdminPassword;
        this.dbCA = dbCA;
    }

    private getAwsSigner(): Signer {
        logger.info(`Creating AWS Signer for RDS/Aurora connection (host: ${this.dbHost}, username: ${this.dbUsername})`);
        return new Signer({
            hostname: this.dbHost,
            port: 5432,
            username: this.dbUsername,
            credentials: this.credentials,
        });
    }

    private async getSequelize(token: string): Promise<Sequelize> {
        logger.info(`Creating Sequelize instance for RDS/Aurora connection (host: ${this.dbHost}, dbName: ${this.dbName}, username: ${this.dbUsername})`);
        return new Sequelize(
            this.dbName,
            this.dbUsername,
            token,
            {
                host: this.dbHost,
                dialect: "postgres",
                define: {
                    freezeTableName: true,
                },
                dialectOptions: {
                    ssl: {
                        ca: this.dbCA
                    }
                },
                pool: {
                    acquire: 120000
                },
                logging: console.log
            }
        );
    }

    public async sync(updateDbSchema: boolean = false): Promise<void> {
        if (!this.sequelize) {
            throw new Error("Sequelize instance is not initialized. Call init() first.");
        }
        logger.info(`Syncing database models`);
        await this.sequelize.sync({ alter: updateDbSchema });
    }

    private async createDatabase(): Promise<boolean> {
        var databaseCreated = false;
        if (this.dbAdminUsername && this.dbAdminPassword) {
            // Create the database if it doesn't exist
            const client = new Client({
                host: this.dbHost,
                user: this.dbAdminUsername,
                password: this.dbAdminPassword,
                port: 5432,
                database: "postgres",
                ssl: {
                    ca: this.dbCA
                }
            });
            logger.info(`Opening connection to database server ${this.dbHost}.`);
            await client.connect();
            try {
                logger.info(`Checking if database ${this.dbName} exists`);
                const res = await client.query(`SELECT datname FROM pg_catalog.pg_database WHERE datname = '${this.dbName}'`);

                if (res.rowCount === 0) {
                    logger.info(`${this.dbName} database not found, creating it.`);
                    await client.query(`CREATE DATABASE "${this.dbName}";`);
                    logger.info(`Successfully created database ${this.dbName}.`);
                    logger.info(`Creating database user ${this.dbUsername}.`);
                    await client.query(`CREATE USER "${this.dbUsername}";`);
                    logger.info(`Successfully created database user ${this.dbUsername}`);
                    logger.info(`Assigning user permissions.`);
                    // await client.query(`GRANT USAGE ON SCHEMA public TO "${this.dbUsername}"; GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "${this.dbUsername}";`);
                    await client.query(`GRANT rds_iam TO "${this.dbUsername}";`);
                    await client.query(`GRANT ALL PRIVILEGES ON DATABASE "${this.dbName}" TO "${this.dbUsername}";`);
                    logger.info(`Successfully assigned user permissions.`);
                    // We have created the database and user, so we can return true
                    databaseCreated = true;
                } else {
                    logger.info(`${this.dbName} database exists.`);
                }
            }
            catch (error) {
                logger.error(`Failed to create database`, error);
            }
            finally {
                await client.end();
                logger.info(`Closed connection to database server ${this.dbHost}.`);
            }
        }
        else {
            logger.warn(`No admin username or password provided. Skipping database creation check.`);
        }
        return databaseCreated;
    }


    private async assignDatabaseSchemaPermissions(): Promise<void> {
        if (this.dbAdminUsername && this.dbAdminPassword) {
            // Create the database if it doesn't exist
            const client = new Client({
                host: this.dbHost,
                user: this.dbAdminUsername,
                password: this.dbAdminPassword,
                port: 5432,
                database: this.dbName,
                ssl: {
                    ca: this.dbCA
                }
            });
            logger.info(`Opening connection to database server ${this.dbHost}.`);
            await client.connect();
            try {
                logger.info(`Assigning database schema permissions.`);
                await client.query(`GRANT USAGE ON SCHEMA public TO "${this.dbUsername}";`);
                await client.query(`GRANT CREATE ON SCHEMA public TO "${this.dbUsername}";`);
                logger.info(`Successfully assigned user permissions.`);
            }
            catch (error) {
                logger.error(`Failed to assign database schema permissions`, error);
            }
            finally {
                await client.end();
                logger.info(`Closed connection to database server ${this.dbHost}.`);
            }
        }
        else {
            logger.warn(`No admin username or password provided. Skipping database creation check.`);
        }
    }

    public async init(): Promise<void> {
        logger.info(`Connecting to database`);

        // Make sure we have a database
        if (await this.createDatabase()) {
            // Assign schema permissions to the user
            await this.assignDatabaseSchemaPermissions();
        }

        // Get the AWS Signer
        const signer = this.getAwsSigner();

        //Get a new token
        const token = await signer.getAuthToken(); // Valid for 15 minutes?

        // Create a new Sequelize instance with the token
        this.sequelize = await this.getSequelize(token);

        // Authneticate to the database
        await this.sequelize.authenticate();
        logger.info('Connection has been established successfully.');

        // Build the models
        this.Product = this.sequelize.define("products", {
            id: {
                type: DataTypes.STRING,
                allowNull: false,
                primaryKey: true,
            },
            name: {
                type: DataTypes.STRING,
                allowNull: false,
            },
            description: {
                type: DataTypes.STRING(2048),
                allowNull: false,
            },
            picture: {
                type: DataTypes.STRING,
                allowNull: false,
            },
            priceUsd_currencyCode: {
                type: DataTypes.STRING,
                allowNull: false,
            },
            priceUsd_units: {
                type: DataTypes.INTEGER,
                allowNull: false,
            },
            priceUsd_nanos: {
                type: DataTypes.INTEGER,
                allowNull: false,
            },
            productCategory_id: {
                type: DataTypes.INTEGER,
                allowNull: false,
            },
        });

        this.ProductTranslation = this.sequelize.define("productTranslations", {
            id: {
                type: DataTypes.INTEGER,
                autoIncrement: true,
                primaryKey: true
            },
            language: {
                type: DataTypes.STRING,
                allowNull: false,
            },
            description: {
                type: DataTypes.STRING(2048),
                allowNull: false,
            },
            product_id: {
                type: DataTypes.STRING,
                allowNull: false,
            },
        });

        this.ProductCategory = this.sequelize.define("productCategories", {
            id: {
                type: DataTypes.INTEGER,
                autoIncrement: true,
                primaryKey: true
            },
            category: {
                type: DataTypes.STRING,
                allowNull: false,
            }
        });

        this.ProductState = this.sequelize.define("productstate", {
            key: {
                type: DataTypes.STRING(20),
                primaryKey: true
            },
            value: {
                type: DataTypes.JSONB
            },
        }, { timestamps: false });
    }
}