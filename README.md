# mobile-release-workflows

The shared release pipeline for Appier mobile SDKs. Design: MT-9607 proposal in
`plaxieappier/sdk-dev-docs` (`products/appier-one-sdk/proposals/2026-10-21-MT-9607_shared-release-workflow.md`).
When something goes wrong, see [RUNBOOK.md](RUNBOOK.md).

| Path | What it is |
| --- | --- |
| `.github/workflows/prepare-release.yml` | Reusable: cut or reuse `release/X.Y.Z` (or `hotfix/X.Y.Z`), sync version files. Stable: regenerate the CHANGELOG section and open or update the PR to `master`. RC: tag the commit and dispatch `release` |
| `.github/workflows/tag-on-merge.yml` | Reusable: when a `release/*` or `hotfix/*` PR merges to `master`, tag the merge commit and dispatch the caller's `release.yml` on it |
| `.github/workflows/release.yml` | Reusable release skeleton, run on a tag: prepare → build → `production` approval → publish → GitHub Release → merge-back → Slack; withdraws the tag when it fails before publishing |
| `actions/<platform>/<stage>` | Platform adapters, see [Adapters](#adapters) |
| `release-tool/` | Python CLI holding the release decision logic; Seam 1 |
| `e2e/` | Seam 2: drives the fixture repo through the pipeline, see [e2e/README.md](e2e/README.md) |
| `scripts/prepare-release.sh` | Git steps of `prepare-release`, runnable locally against any remote |
| `scripts/release-central.sh` | Releases this repo: runs both seams, then tags `vX.Y.Z` and moves `v1` |
| `cliff.toml` | Default git-cliff config: conventional-commit groups and Jira links. A repo's own `cliff.toml` wins |

## Release flow

1. **RCs.** Dispatch `prepare-release` with `X.Y.Z-rc.N`. The bump is committed on
   `release/X.Y.Z` (cut from `develop` the first time), tagged, and released as a prerelease
   (npm dist-tag `rc`). QA installs it. Fixes go into `release/X.Y.Z` by PR; the next RC is
   `rc.N+1`.
2. **Stable.** When QA passes, dispatch `prepare-release` with `X.Y.Z`. It writes `X.Y.Z` back,
   regenerates the CHANGELOG section, and opens or updates the PR to `master`. Merging it is QA's
   sign-off.
3. **Release.** The merge tags `vX.Y.Z` and dispatches `release`. A `production` reviewer approves;
   it publishes, creates the GitHub Release, and merges `master` back into `develop`.
4. **Hotfix.** Dispatch `prepare-release` with `base: hotfix` and the next patch (`X.Y.Z+1-rc.1`
   first). The branch `hotfix/X.Y.Z+1` is cut from the latest stable tag; then as above. Its
   merge-back also opens PRs into open `release/*` branches, merged by hand.

## Using it from an SDK repo

1. Add `.github/release-config.yml`:

   ```yaml
   platform: flutter            # flutter | react-native | android | ios
   working-directory: sdk       # default "."; CHANGELOG.md lives here
   tag-prefix: v                # default "v"
   channels: [public]           # default [public]; react-native also supports internal
   version:
     primary: {file: sdk/pubspec.yaml, path: .version}
     sync:
       - {file: sdk/android/build.gradle, regex: "ext\\.appier_sub_version = '([^']+)'"}
   native-deps:                 # optional; drift is warned about, never blocks
     - {name: AppierFramework, repo: appier/appier-ios-framework, file: sdk/ios/appier_flutter.podspec, regex: "'AppierFramework', '([^']+)'"}
   ```

   A locator is `{file, path}` (yq-style path into YAML or JSON) or `{file, regex}` with exactly
   one capture group. `file` is relative to the repo root.

2. Give the repo the release GitHub App: install the App on the SDK repo and on this repo,
   set the variable `RELEASE_APP_ID` and the secret `RELEASE_APP_PRIVATE_KEY` (org-level in
   `plaxieappier`). App permissions: Contents read/write, Pull requests read/write, Actions
   read/write, Checks read, Commit statuses read. Optionally set `SLACK_RELEASE_WEBHOOK`.

3. Create the `production` environment: required reviewers `sdk-release-approvers`, prevent
   self-review, deployment tags `v*`. Protect `release/*` and `hotfix/*` from deletion, and allow
   auto-merge.

4. Add three caller workflows, each `uses: plaxieappier/mobile-release-workflows/.github/workflows/<name>@v1`
   with `secrets: inherit`:

   | Caller | Trigger | Requirements |
   | --- | --- | --- |
   | `prepare-release.yml` | `workflow_dispatch` with `version`, `base` (`develop` \| `hotfix`), `dry-run` (default `true`) | job `permissions: contents: read` |
   | `tag-on-merge.yml` | `pull_request: {types: [closed], branches: [master]}` | job `permissions: contents: read` |
   | `release.yml` | `workflow_dispatch` with `channel` and boolean `dry-run` (default `true`) | must be named `release.yml` (npm trusted publishing is bound to it); job `permissions: contents: read, id-token: write, packages: write`; job `concurrency: {group: release-<repo>, cancel-in-progress: false}` |

   When calling a fork or a branch, also pass `central-repo` and `central-ref` so release-tool and
   the adapters load from the same place as the workflow.

## Adapters

Each platform provides `actions/<platform>/{setup,verify,test,build,is-published,publish}`.
Every action takes `working-directory`, `version`, `channel`, and `dry-run`. The skeleton names
platforms only in its dispatch-table blocks, so adding one means writing these six actions and
adding one line per block.

| Stage | Contract |
| --- | --- |
| `setup` | Install the toolchain from the repo's version file, and dependencies |
| `verify` | Pre-publish checks; fail on a channel the platform doesn't support |
| `test` | Unit tests |
| `build` | Produce the artifact; export `RELEASE_ARTIFACT_PATH` |
| `is-published` | Export `RELEASE_PUBLISHED=true\|false` for the channel's registry |
| `publish` | Publish `RELEASE_ARTIFACT_PATH` under `RELEASE_DIST_TAG`, honouring `dry-run`; export `RELEASE_ARTIFACT_URL` |

## release-tool

```
release-tool config validate              # exit 1 naming the offending field
release-tool config get <key>             # platform | working-directory | tag-prefix | channels
release-tool version write <X.Y.Z[-rc.N]> # rewrite every version file
release-tool version verify <tag>         # exit 1 listing every file that disagrees
release-tool classify <version>           # prerelease=, dist-tag=, tag=
release-tool hotfix-check <v> --tags F    # print the stable tag a hotfix starts from, or exit 1
release-tool native-drift --tags-dir D    # one warning per outdated native pin; always exit 0
release-tool native-drift --list-repos    # native repos to fetch tags for
release-tool changelog drop <v> --file F  # remove one version's section
release-tool ci verify --runs F --statuses F --exclude-path P
                                          # exit 0 CI passed, 1 failed, 2 still running
release-tool plan --tag-exists B --published B
                                          # publish | skip-publish | fail
release-tool slack-message --outcome O …  # the Slack payload for a release outcome
```

The `config`, `version`, `classify`, `hotfix-check`, and `native-drift` commands take
`--repo <dir>` (default `.`).

## Versioning

Callers pin the moving major tag `v1`. `scripts/release-central.sh X.Y.Z` runs the unit tests and
the Seam 2 suite against `main`, then tags `vX.Y.Z` and moves `v1`. A breaking change to a
workflow's inputs, outputs, or secrets, to the adapter contract, or to `release-config.yml`
requires `v2`.

## Development

```
python3 -m venv .venv && .venv/bin/pip install -e 'release-tool[test]' git-cliff
.venv/bin/pytest -q release-tool
```
