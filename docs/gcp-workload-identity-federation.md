# Plan: move all demo repos to GCP Workload Identity Federation

Status: proposal. Nothing here is implemented yet.

## Why

- `opentelemetry-demo` and `easytrade` log in to Google Artifact Registry (GAR) with a long-lived
  service-account JSON key stored as the `GAR_CREDENTIALS` secret (`docker login -u _json_key_base64`,
  `helm registry login -u _json_key_base64`).
- `smartfreight` already uses Workload Identity Federation (WIF): `google-github-actions/auth@v3` with
  `token_format: access_token`, then `docker login --username oauth2accesstoken`.
- Static keys must be rotated, can leak, and may be forbidden by org policy. The shared reusable
  workflows only support keys, so a WIF repo (smartfreight) cannot use `reusable-build.yaml` today.

Goal: one auth mechanism (WIF) in every repo and in the shared reusables, no `GAR_CREDENTIALS` secret.

## Current state

| Repo | Org | GAR auth today |
|---|---|---|
| opentelemetry-demo | Dynatrace | `GAR_CREDENTIALS` key |
| easytrade | Dynatrace | `GAR_CREDENTIALS` key |
| smartfreight | Dynatrace-Internal | WIF, pool `github-actions` / provider `github-actions-oidc` in project `959021067757`, SA `gha-smartfreight-0342ded8@dynatrace-demoability.iam.gserviceaccount.com` |

Key consumers in this repo:
- `.github/actions/docker-gar-login/action.yaml` (reads `GAR_CREDENTIALS` env)
- `.github/actions/build-push-helm/action.yaml` (`credentials` input, `helm registry login`)
- `.github/workflows/reusable-build.yaml` (`GAR_CREDENTIALS` secret passed to both)

## Target design

### 1. GCP side (per repo, via the existing smartfreight pattern)
- Reuse the existing pool/provider; do not create new pools.
- One service account per repo, e.g. `gha-<repo>-<suffix>@dynatrace-demoability.iam.gserviceaccount.com`,
  with only `roles/artifactregistry.writer` on the `docker` and `helm` repositories (`europe` location).
- Allow the repo to impersonate its SA: `roles/iam.workloadIdentityUser` on the SA for principal
  `principalSet://iam.googleapis.com/projects/959021067757/locations/global/workloadIdentityPools/github-actions/attribute.repository/<org>/<repo>`.
- Check the provider's attribute condition covers `Dynatrace/*` as well as `Dynatrace-Internal/*`
  (smartfreight is in a different org). Widen it if needed.
- Manage this in the existing IaC (devops / Terragrunt), not by hand.

### 2. Shared reusables (this repo)
- New composite action `.github/actions/gcp-auth` (wraps `google-github-actions/auth@v3`,
  `token_format: access_token`; outputs `access_token`).
- `docker-gar-login`: replace the key login with `oauth2accesstoken` + the access token.
- `build-push-helm`: replace `credentials` (key) input with `access-token`; login with
  `--username oauth2accesstoken`.
- `reusable-build.yaml`: new inputs `gcp-workload-identity-provider` and `gcp-service-account`
  (no secrets involved; both are identifiers). When set, run `gcp-auth` before the login/push steps.
  Jobs already have `permissions: id-token: write`; `build-push-helm` job needs it added.
- Transition: keep `GAR_CREDENTIALS` secret as optional fallback while repos migrate; remove it in the
  last step. Callers choose by passing WIF inputs or the secret.
- Access token lifetime is 1h by default; long builds should set `access_token_lifetime`.

### 3. Repo migration order
1. opentelemetry-demo (this repo): GCP SA + binding, switch `build-on-main.yaml` / `build-pr.yaml`
   to pass the WIF inputs. Note: PR builds from forks have no OIDC token; `push: false` PR builds
   must not require auth (already gated by `inputs.push`).
2. easytrade: same, plus its local `build-push-images` / `build-push-helm` actions or switch it to the
   shared ones (see the compatibility notes: compose-file in matrix, image variable names, images file).
3. smartfreight: drop its local auth steps and use the shared reusable with its existing SA.
4. Remove `GAR_CREDENTIALS` from all repo/org secrets and the `workflow_call.secrets` blocks.
5. Delete the old SA keys in GCP.

### 4. Open questions
- Does org policy allow the Dynatrace pool provider to trust repos in both `Dynatrace` and
  `Dynatrace-Internal`? (decides whether one provider or two)
- Is one SA per repo required, or can repos share one writer SA? (per-repo is least privilege)
- Do any workflows push from `workflow_dispatch` on non-main branches? The provider condition may
  restrict refs; verify it allows branches used for dev builds.
- Other users of `GAR_CREDENTIALS` outside these three repos (deploy workflows, Argo, etc.)?

## Verification
- In a test branch, run `build-on-main` with `push: true`; confirm images and charts land in GAR and
  no `GAR_CREDENTIALS` is referenced.
- `gcloud artifacts docker images list` / `helm pull` for the pushed version.
- Confirm a PR build (`push: false`) still passes without any GCP auth.
- After removing the secret, re-run to prove nothing depends on it.
