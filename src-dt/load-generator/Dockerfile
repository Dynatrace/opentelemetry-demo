FROM golang:1.24.5-alpine3.22 AS build

RUN apk add --no-cache gcc libc-dev

WORKDIR /build

COPY ["src/go.*", "./"]

RUN go mod download

COPY ["src/", "."]

RUN go build -ldflags="-linkmode=external" -o load-generator

FROM alpine:3.22

WORKDIR /app

COPY --from=build ["/build/load-generator", "."]

CMD ["/app/load-generator"]
