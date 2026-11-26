# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Dynatrace fork of `open-telemetry/opentelemetry-demo` (the "Astroshop" microservice demo). Keep upstream-owned code in `src/` untouched so upstream merges stay clean; Dynatrace delta lives in `dynatrace/`, `src-dt/`, `charts/`, `.github/`, `.env.override`, `Makefile`.

**Always open PRs against `Dynatrace/opentelemetry-demo`** (the fork, `origin`), never against upstream `open-telemetry/opentelemetry-demo`. With `gh`, pass `--repo Dynatrace/opentelemetry-demo`.

## Commands

All via `make` (wraps `docker compose --env-file .env --env-file .env.override`):

- `make build` / `make start` / `make start-minimal` / `make stop`
- Single service: `make redeploy service=frontend`, `make restart service=frontend`, `make build-and-push-service service=frontend`
- Tests: `make run-tests` (frontend + trace-based); `make run-tracetesting SERVICES_TO_TEST="cart"` for a subset
- Lint/checks: `make check` (misspell, markdownlint, license, links), `make yamllint`, `make fix`
- Protobuf: `make generate-protobuf` / `make docker-generate-protobuf`, then `make check-clean-work-tree`

Always keep `.env.override` in the compose env chain; without it the custom Dynatrace Dockerfiles are not used and images get the wrong name.

## Architecture

- **Source layout (three roots):**
  - `src/` – upstream services, don't edit.
  - `dynatrace/` – Dynatrace-owned: shadow `Dockerfile.{checkout,frontend,payment,productcatalog}` (still `COPY` from `src/`), a rewritten `load-generator`, `postgres`, `consumer-service`, `cloud-backend` (Lambdas/data pipeline, per-stage config in `config.yaml`, see its README for OneAgent layer updates), `cloud-backend-load-generator`.
  - `src-dt/` – fully custom services with no upstream equivalent.
- **Overrides wiring:** `.env.override` points upstream compose vars (`CHECKOUT_DOCKERFILE`, `FRONTEND_DOCKERFILE`, `LOAD_GENERATOR_DOCKERFILE`, `IMAGE_NAME`, …) at the `dynatrace/` Dockerfiles. Root `docker-compose.yml` is the build source of truth for upstream services.
- **Extra images:** `.github/images.yaml` lists images not in the root compose (consumer-service, cloud-backend ones, etc.) with `directory`, `compose-file`, `registry-type` (`gar`|`ecr`), `registry`, optional `pr` overrides. The CI build matrix = these + every service with a `build:` in root `docker-compose.yml` (scanned by the `list-build-services` action).
- **Charts:** `charts/astroshop`, `astroshop-consumer-service`, `astroshop-cloud-backend` (Helm; pushed to OCI registry in CI; image tag path patched at build time).

## CI / releases

- `build-pr.yaml` skips draft PRs (`build` job `if` includes `github.event.pull_request.draft != true`; `ready_for_review` is a trigger type so marking ready starts the build). Keep this when editing triggers.
- `build-pr.yaml` and `build-on-main.yaml` chain `reusable-calc-version` → `reusable-build` → (`reusable-promote-release` on release). `calc-version` gates the build via `skip-build`.
- **Reusable workflows are consumed from other repos** (see `docs/reusable-workflows.md`): composite actions are referenced by full path `Dynatrace/opentelemetry-demo/.github/actions/<x>@main`, never `./.github/actions/...`. `reusable-build` is parametrized by inputs (registries, region, bucket, `lambda-matrix`, `helm-matrix`) whose defaults are this repo's values — keep defaults working for the in-repo callers when changing it. Secrets are declared in `workflow_call.secrets` (`AWS_ROLE`, `GAR_CREDENTIALS`).
- Versioning (GitVersion 6, `.github/actions/calc-version`): push to `main` bumps **minor** and releases; other branches get patch bump + `-<branch>-<sha>` suffix; control with `+semver: major|minor|fix|skip` in commit/squash message. Details: `dynatrace/docs/versioning.md`.
- Conventional-commit style titles with PR number (`feat(calc-version): … (#93)`).
