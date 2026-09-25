FROM public.ecr.aws/docker/library/node:22-alpine

WORKDIR /usr/local/app

ADD package.json .

RUN npm install

ADD queueProcessor.js instrument.js ./

CMD [ "node", "--require", "./instrument.js" , "queueProcessor.js" ]