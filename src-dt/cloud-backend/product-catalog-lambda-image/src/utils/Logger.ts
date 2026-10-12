import { LogFn, Logger, pino } from "pino";

function logMethod (this: Logger, args : Parameters<LogFn>, method : LogFn, level : number) {
  if (args.length === 2) {
    args[0] = `${args[0]} %j`
  }
  method.apply(this, args)
}

export const logger = pino({
  redact: {
    paths: ['req.headers.authorization'],
    remove: true
  },
  name: 'productcatalogbackend',
  level: process.env.PINO_LOG_LEVEL || 'info',
  hooks: { logMethod }
});