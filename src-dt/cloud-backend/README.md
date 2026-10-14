# cloud-backend

Astroshop cloud-backend services, built and deployed per stage (`dev`, `hardening`, `prod`):

| Directory | What it is |
|---|---|
| `product-catalog-lambda-image` | Container-image Lambda for the product catalog admin. `Dockerfile.oneagent` adds the Dynatrace OneAgent Lambda layer on top of the base image, one image per stage. |
| `raw-data-persistence`, `reporting` | Zip-packaged Lambdas. |
| `data-processing`, `processed-data-persistence` | Data pipeline services. |

`compose.yaml` builds the images, `config.yaml` holds the per-stage build configuration
(the OneAgent layer ARNs).

## Updating the OneAgent layer for product-catalog-lambda-image

The image bundles the OneAgent Lambda layer, which the build reads from `config.yaml`
(`stage.<stage>.agent.arn_layer_pattern_nodejs`). `update_lambda_arns.sh` refreshes those ARNs:

1. Fetches the latest layer ARN for each stage from its Dynatrace tenant
   (`GET /api/v1/deployment/lambda/layer`, `x86`, `us-east-1`, with collector).
2. Copies the layer into the AWS account you are connected to (`us-east-1`), verifying size and
   SHA-256 of the download and of the published copy. A layer already present in the account is reused.
3. Writes the ARN of the copy to `config.yaml` (`nodejs` and `python`) and prints the diff.

### Steps

1. Log in to AWS and check the account: `aws sts get-caller-identity`.
2. Export the tenant URL and a platform token (scope `fleet-management:oneagents:download`) per
   stage. They are not stored in git: copy `.env.example.sh` to `.env.sh` (git-ignored) and `source` it:
   ```bash
   export DT_API_URL_DEV=...        # classic API domain, e.g. https://<tenant>.live.dynatrace.com
   export DT_API_URL_HARDENING=...
   export DT_API_URL_PROD=...
   export DT_INSTALL_TOKEN_DEV=...
   export DT_INSTALL_TOKEN_HARDENING=...
   export DT_INSTALL_TOKEN_PROD=...
   ```
3. Run it (needs `aws`, `yq`, `jq`, `curl`, `openssl`):
   ```bash
   ./update_lambda_arns.sh
   ```
4. Review the printed `git diff` and commit `config.yaml`.

The script publishes layer versions to whichever AWS account is connected, so check step 1 first.
