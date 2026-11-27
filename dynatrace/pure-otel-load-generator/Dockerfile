# syntax=docker/dockerfile:1
FROM node:24-trixie-slim AS builder

ENV PUPPETEER_SKIP_DOWNLOAD=true

WORKDIR /build

COPY ["package.json", "package-lock.json", ".npmrc", "./"]
RUN npm ci

COPY ["tsconfig.json", "."]
COPY ["src/" ,"src/"]
RUN npm run build

FROM node:24.11-trixie-slim AS dev

ENV PUPPETEER_CACHE_DIR=/opt/puppeteer \
    FRONTEND_URL=http://frontend \
    CONCURRENCY=2 \
    BROWSER_HEADLESS=true \
    SYNTHETIC_REQUEST_ENABLED=false \
    PAGE_WAIT_UNTIL=load \
    ACTION_DURATION_MS=100

ARG CHROME_LIBS="libasound2 libatk-bridge2.0-0 libatk1.0-0 libcairo2 libcups2 libdrm-dev libgbm-dev libglib2.0-0 libnss3 libpango-1.0-0 libxcomposite1 libxdamage1 libxfixes-dev libxkbcommon-dev libxrandr-dev"

WORKDIR /usr/src/app

RUN apt update \
    && apt upgrade -y \
    && apt install -y ${CHROME_LIBS} \
    && apt install -y dumb-init \
    && apt install -y curl \
    && rm -rf /var/lib/apt/lists/*

COPY ["package.json", "package-lock.json", ".npmrc", "./"]

RUN npm ci --omit=dev \
    && npx puppeteer browsers install chrome \
    && npm cache clean --force

COPY --from=builder ["/build/dist", "./build"]

ENTRYPOINT [ "/usr/bin/dumb-init", "--" ]
CMD [ "node", "./build/index.js" ]
