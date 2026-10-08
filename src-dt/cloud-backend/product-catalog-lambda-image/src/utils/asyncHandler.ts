import { NextFunction, Request, RequestHandler, Response } from 'express';

// Express 4 does not catch rejected promises; an unhandled rejection kills the Lambda runtime before the invocation span is exported.
export const asyncHandler = (fn: (req: Request, res: Response, next: NextFunction) => Promise<unknown>): RequestHandler =>
  (req, res, next) => {
    fn(req, res, next).catch(next);
};