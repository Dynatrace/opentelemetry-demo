import { Buffer } from "buffer";
import { Request, Response, NextFunction } from "express";
import { logger } from '../utils/Logger'

export default class Auth {
    public async isAuthorized(req: Request, res: Response, next: NextFunction) {
        logger.info(`${new Date().toISOString()} | isAuthorized`, req.originalUrl);

        if (!req.headers.authorization) {
            let err = new Error('HTTP Request missing required autorization header!');
            res.setHeader('WWW-Authenticate', 'Basic');
            res.status(401); // Unauthorized
            return next(err);
        }
    
        const admin_user = process.env.PRODUCT_ADMIN_USER;
        if(!admin_user) {
            throw new Error('PRODUCT_ADMIN_USER not set!');
        }
        const admin_password = process.env.PRODUCT_ADMIN_PASSWORD;
        if(!admin_password) {
            throw new Error('PRODUCT_ADMIN_PASSWORD not set!');
        }

        const auth = Buffer.from(req.headers.authorization.split(' ')[1], 'base64').toString().split(':');
        const user = auth[0];
        const pass = auth[1];
    
        if (user == admin_user && pass == admin_password) {
            // If Authorized user
            next();
        } else {
            let err = new Error('Invalid username and/or password!');
            res.setHeader('WWW-Authenticate', 'Basic');
            res.status(401); // Unauthorized
            return next(err);
        }
    }
}