FROM node:24.13.0-alpine AS build

WORKDIR /usr/src/app

COPY ["package*.json", "./"]

RUN npm ci --omit-dev

# -----------------------------------------------------------------------------

FROM node:24.13.0-alpine

RUN apk upgrade --no-cache

USER node
WORKDIR /usr/src/app/

COPY --chown=node:node --from=build ["/usr/src/app/node_modules/", "./node_modules/"]
COPY ["src", "src"]

CMD [ "node", "src/index.js" ]
