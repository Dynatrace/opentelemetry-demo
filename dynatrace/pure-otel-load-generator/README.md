# pure-otel-load-generator (otel-loadgen)

TypeScript / Puppeteer port of the Python/Locust load generator found at
[`dynatrace/load-generator`](../load-generator).

Built on top of [`@demoability/loadgen-core`](https://bitbucket.lab.dynatrace.org/projects/DEM/repos/loadgen-core).

## Deployment

> **NOTE:** the actual deployment on demoability envs happens through argo and is defined [here](https://github.com/Dynatrace/opentelemetry-demo-infrastructure/blob/main/resources/kustomize-components/otel-loadgen/deployment.yaml)

The deployment defined under `k8s` is left as an example or for convenience during testing

## CI

The image is built by this repository's regular release pipeline (entry `pure-otel-load-generator` in
[`.github/images.yaml`](../../.github/images.yaml)) and pushed to
`europe-docker.pkg.dev/dynatrace-demoability/docker/otel-loadgen:<release version>`.

`@demoability/loadgen-core` is resolved from the public GAR npm registry configured in `.npmrc`; no credentials are needed.

## What it does

For each concurrent worker, the generator loops indefinitely and executes
a `browse_and_checkout` task that:

1. Navigates to the frontend homepage and waits for the banner image to load.
2. Picks a random product card and adds it to the cart.
3. Returns to the homepage via "Continue Shopping".
4. Picks a second product card and adds it to the cart.
5. Fills the checkout form with a random persona's details and places the order.

Each task run is assigned a random persona from `people.json` with a fixed
simulated IP and a realistic User-Agent string. These are used to:

- Set the Puppeteer-level User-Agent (`page.setUserAgent`).
- Inject `x-forwarded-for` so Dynatrace resolves geolocation from the simulated IP rather than the container IP.
- Optionally add a `baggage: synthetic_request=true` header so the frontend SSR can route RUM beacons to the internal collector.

Stats are logged to stdout every 30 seconds via `loadgen-core`'s
`StatsRunner`.

## Environment variables

| Variable                    | Default           | Description                                                                                    |
| --------------------------- | ----------------- | ---------------------------------------------------------------------------------------------- |
| `FRONTEND_URL`              | `http://frontend` | Base URL of the OTel demo frontend                                                             |
| `CONCURRENCY`               | `2`               | Number of parallel browser workers                                                             |
| `BROWSER_HEADLESS`          | `true`            | Run Chromium headless (`false` opens a window, useful locally)                                 |
| `SYNTHETIC_REQUEST_ENABLED` | `false`           | Add `baggage: synthetic_request=true` header                                                   |
| `PAGE_WAIT_UNTIL`           | `load`            | Puppeteer navigation wait strategy: `load`, `domcontentloaded`, `networkidle0`, `networkidle2` |
| `ACTION_DURATION_MS`        | `100`             | Delay between checkout form field fills (ms)                                                   |

## Local development

### Prerequisites

- Node.js 22+

### Install and build

```bash
npm ci
npm run build
```

### Run locally against a local OTel demo

```bash
# Uses ts-node (no build step). Defaults: 1 worker, visible browser, no synthetic header.
npm run start:local

# Override the frontend URL:
FRONTEND_URL=http://my-otel-demo:8080 npm run start:local

# More workers, still headless-off:
FRONTEND_URL=http://my-otel-demo:8080 CONCURRENCY=3 npm run start:local
```

All env vars listed in the table above can be prefixed the same way.
The script bakes in local-friendly defaults so you don't have to spell them
out every time:

| Variable                    | Default for `start:local` |
| --------------------------- | ------------------------- |
| `FRONTEND_URL`              | `http://localhost:8080`   |
| `CONCURRENCY`               | `1`                       |
| `BROWSER_HEADLESS`          | `false`                   |
| `SYNTHETIC_REQUEST_ENABLED` | `false`                   |

## Docker

### Build

```bash
docker compose build   # or: docker build -t otel-loadgen .
```

### Run

```bash
docker run --rm \
  -e FRONTEND_URL=http://your-otel-demo:8080 \
  -e CONCURRENCY=2 \
  otel-loadgen
```
