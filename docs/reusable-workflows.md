# Reusable workflows

Workflows in `.github/workflows/reusable-*.yaml` can be called from other repositories.
They reference their composite actions by full path
(`Dynatrace/opentelemetry-demo/.github/actions/<name>@main`), because `./.github/actions/...`
inside a reusable workflow resolves in the *caller* repo.

**Prerequisite:** in this repo, Settings → Actions → General → Access →
"Accessible from repositories in the organization".

Secrets are declared explicitly; pass them with `secrets:` (or `secrets: inherit` in the same org).

## reusable-calc-version.yaml

| Input | Default | Description |
|---|---|---|
| `release-branch` | `main` | Branch that triggers releases |

Outputs: `version`, `is-release`, `skip-build`, `already-released` (deprecated).
Checks out full history. Honors `+semver: skip|none` in commit messages.

## reusable-build.yaml

| Input | Default | Description |
|---|---|---|
| `push` (required) | | Push images/charts |
| `is-pr` (required) | | Apply `.pr` overrides from images file |
| `version` (required) | | Version from calc-version |
| `container-registry` | `europe-docker.pkg.dev/dynatrace-demoability/docker/astroshop` | Registry for root compose images |
| `helm-registry` | `oci://europe-docker.pkg.dev/dynatrace-demoability/helm` | OCI chart registry |
| `aws-region` | `us-east-1` | AWS region |
| `lambda-artifacts-bucket` | `astroshop-artifacts-bucket` | S3 bucket for Lambda zips |
| `images-file` | `.github/images.yaml` | Extra images list (caller repo) |
| `compose-file` | `docker-compose.yml` | Root compose file (caller repo) |
| `lambda-matrix` | astroshop Lambdas | JSON `[{service, runtime, runtime-version, source-dir}]`; `[]` skips |
| `helm-matrix` | astroshop charts | JSON `[{chart-path, image-tag-path}]`; `[]` skips |

Secrets: `AWS_ROLE` (OIDC role; ECR, OneAgent layer, Lambda), `GAR_CREDENTIALS` (GAR + chart push).
Caller needs `permissions: id-token: write, contents: read`.

## reusable-promote-release.yaml

| Input | Default | Description |
|---|---|---|
| `version` (required) | | Creates tag `v<version>` and release |
| `trigger-deploy` | `false` | Dispatch deploy workflow |
| `deploy-workflow-name` | `deploy.yaml` | Must exist in caller repo if `trigger-deploy` |
| `artifact-name` / `artifact-dir` | | Optional release artifacts |

Caller needs `permissions: contents: write, actions: write`.

## Caller example

```yaml
jobs:
  calc-version:
    uses: Dynatrace/opentelemetry-demo/.github/workflows/reusable-calc-version.yaml@main
  build:
    needs: calc-version
    if: needs.calc-version.outputs.skip-build == 'false'
    permissions:
      id-token: write
      contents: read
    uses: Dynatrace/opentelemetry-demo/.github/workflows/reusable-build.yaml@main
    with:
      push: true
      is-pr: false
      version: ${{ needs.calc-version.outputs.version }}
      container-registry: europe-docker.pkg.dev/my-project/docker/myapp
      lambda-matrix: "[]"
      helm-matrix: '[{"chart-path":"charts/myapp","image-tag-path":".tag"}]'
    secrets:
      AWS_ROLE: ${{ secrets.AWS_ROLE }}
      GAR_CREDENTIALS: ${{ secrets.GAR_CREDENTIALS }}
```

## Caveats

- Composite actions are pinned to `@main`: action changes in a PR are not exercised by
  same-repo PR builds until merged.
- `list-build-services` expects docker-compose build contexts and an images file in the caller repo.
