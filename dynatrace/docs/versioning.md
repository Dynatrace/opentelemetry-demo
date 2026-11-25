# Versioning and releases

Versions are calculated from git history by the composite action
[`.github/actions/calc-version`](../../.github/actions/calc-version/action.yaml) (GitVersion 6). The same action is used by
this repository and by other repositories (`Dynatrace/opentelemetry-demo/.github/actions/calc-version@<tag>`).

Tags are `v<major>.<minor>.<patch>` (`v0.4.16`); unprefixed tags (`0.4.16`) are read too.

## Rules in short

| Where the build runs | Version | Release? |
|---|---|---|
| push to `main` | latest tag on `main` + **minor** bump (or the bump from a `+semver:` marker) | yes: tag `v<version>` and GitHub release |
| pull request into `main` | what `main` would get after the merge, `<version>-pr<N>-<sha>` | no |
| any other branch | latest tag **reachable from that branch** + **patch** bump, `<version>-<branch>-<sha>` | no |
| manual run of `build-on-main` on a non-`main` branch, `release` **unchecked** (dev build) | latest tag reachable from the branch + patch bump, `<version>-<branch>-<sha>` | no: images and charts are pushed with that version, no tag, no GitHub release |
| manual run of `build-on-main` on a non-`main` branch, `release` **checked** | latest tag reachable from the branch + patch bump, plain `<version>` | yes: tag and release on that branch |

Key points:

- `main` bumps **minor** on every merge. Patch releases are reserved for maintenance branches.
- A branch only looks at tags reachable from its own history. A branch cut from `v0.8.0` never sees `v1.1.0`,
  which exists only on `main`. (For non-`main` branches the action hides `main`/`master` from GitVersion, otherwise
  GitVersion falls back to `main` as source branch and takes its newest tag as base.)
- Tag the release only after the build and publish succeeded, so a failed run leaves no tag and can be re-run.

## Commit message markers

Put a marker in the commit message (for squash merges: in the PR title / squash message that lands on `main`).

| Marker | Effect |
|---|---|
| `+semver: major` / `+semver: breaking` | major bump |
| `+semver: minor` / `+semver: feature` | minor bump |
| `+semver: fix` / `+semver: patch` | patch bump (the branch default already is patch, see below) |
| none | branch default: **minor** on `main`, **patch** on other branches |

The highest bump among the commits since the last tag wins.

> `+semver: none` / `skip` no longer lowers the bump on `main` (the minor default is a floor). Instead the action sets
> the output `skip-build=true` when the head commit message of a **push** contains `+semver: skip` or `+semver: none`
> (case-insensitive, with or without the space), and `build-on-main` does not build or release. Use it for changes that
> must not produce a new version (docs, CI-only changes). For a squash merge put it in the PR title or the squash
> message. Manual runs and PR builds ignore it.

## Branch names

- `main` / `master`: release branch.
- Maintenance branches for older versions: **`patch/<major>.<minor>`**, e.g. `patch/0.8`.
- Feature branches: any name, `feature/*` included.
- Do **not** use `hotfix/*`, `release/*`, `support/*` or `develop`: these are GitVersion built-in branch types that
  expect `main` as source branch, and the run fails with `No base versions determined on the current branch`.

## Examples

Real runs from the test repository `version-tests` (tags in the left column existed before the commit).

### Normal releases from `main`

| Commit on `main` | Latest tag | Result |
|---|---|---|
| `Increase max-file limit` | `v0.6.0` | `v0.7.0` |
| `unmarked change` | `v0.7.0` | `v0.8.0` |
| `breaking change +semver: major` | `v0.8.0` | `v1.0.0` |
| `another unmarked change` | `v1.0.0` | `v1.1.0` |

### Pull request

A PR build runs on the merge result of the PR and `main`, so it previews the release `main` will produce:
`main` at `v0.6.0` -> PR build `0.7.0-pr16-399f8c7`. A branch that was cut long ago (say at `v0.4.0`) shows the
same: the version is relative to `main`'s newest tag, not to the branch's start.

### Dev build from a feature branch

To try a branch without releasing anything, run the workflow manually with `release` left unchecked (the default):

```bash
gh workflow run build-on-main.yaml --ref my-feature
```

The build pushes images and charts tagged `1.2.1-my-feature-016cf10` and stops there: no tag, no GitHub release.
(A manual run on `main` itself always releases.)

### Patching an older release

Release `v0.8.0` is long gone and `main` is at `v1.1.0`. A fix is needed for the `0.8` line only.

```bash
# 1. branch from the release tag. Name it patch/<major>.<minor>, see "Branch names" below.
git fetch --tags
git checkout -b patch/0.8 v0.8.0

# 2. commit the fix (a commit that exists on the branch only, or cherry-picked from main) and push
git commit -am "fix: ..."
git push -u origin patch/0.8

# 3. run the release manually: Actions -> "Build and push astroshop" -> Run workflow -> Branch: patch/0.8,
#    tick "release"
gh workflow run build-on-main.yaml --ref patch/0.8 -f release=true
```

Result: `v0.8.1` (tag and release created on `patch/0.8`). Repeat steps 2-3 for `v0.8.2`, and so on. `main` is not
affected: its next release is still `v1.2.0`.

| Run | Branch | Version |
|---|---|---|
| push | `main` | `v1.1.0` |
| manual | `patch/0.8` | `v0.8.1` |
| manual | `patch/0.8` | `v0.8.2` |
| push | `main` | `v1.2.0` |

To make a new minor out of a maintenance branch (`v0.9.0`) use `+semver: minor` in one of its commits.

Notes:

- The branch must contain the workflow change that passes `release-branch` for `workflow_dispatch` (cut it from a tag
  that has it, or cherry-pick it).
- A manual run on a non-`main` branch releases only with `release=true`; without it, it is a dev build.
- If the computed version already exists the build is skipped (`skip-build=true`). This happens when a tag
  already sits on the same commit as the base tag; add a commit with a marker to move on.

## Using the action in another repository

```yaml
jobs:
  calc-version:
    runs-on: ubuntu-24.04
    outputs:
      version: ${{ steps.v.outputs.version }}
      is-release: ${{ steps.v.outputs.is-release }}
      skip-build: ${{ steps.v.outputs.skip-build }}
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0            # all tags and history are required
      - id: v
        uses: Dynatrace/opentelemetry-demo/.github/actions/calc-version@v0.5.0
        with:
          # releases happen from this branch; ref_name only for a manual run that asks for a release
          release-branch: ${{ github.event_name == 'workflow_dispatch' && inputs.release && github.ref_name || 'main' }}
```

Outputs:

| Output | Meaning |
|---|---|
| `version` | the version; plain `1.2.3` on a release build, `1.2.3-<label>-<sha>` otherwise |
| `is-release` | `true` when the current branch equals `release-branch` |
| `skip-build` | `true` when build and publish must be skipped: tag `v<version>` already exists, or (push only) the commit message has `+semver: skip` / `+semver: none`. Use `if: needs.calc-version.outputs.skip-build == 'false'` |
| `already-released` | **deprecated**, use `skip-build`. `true` when tag `v<version>` exists |

Pin the action to a tag (`@v0.5.0`) for reproducible versions, or to `@main` to always get the latest rules.
The `main` minor-by-default rule and the maintenance-branch handling apply from `v0.5.0`; older tags keep the previous
behaviour (patch by default, `main` could pick up an unrelated newest tag on maintenance branches).
