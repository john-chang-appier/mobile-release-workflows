# Seam 2: end-to-end checks on the fixture repo

`e2e/run.py` drives `john-chang-appier/mobile-release-fixture` (callers pinned to `@main`, every
publish a dry run) with your `gh` login. `scripts/release-central.sh` runs it before any `v1.x`
tag moves.

| Scenario | What it proves |
| --- | --- |
| `version-mismatch` | A tag whose version files disagree fails in `prepare`, never asks for approval, is withdrawn, and the Slack payload reports the failure |
| `stable-cycle` | `prepare-release X.Y.Z` → release PR → merge → tag on the merge commit → `prepare` and `build` pass → approval requested; cancelling withdraws the tag |
| `rc-cycle` | `prepare-release X.Y.Z-rc.1` commits on `release/X.Y.Z` without a PR, tags it, and dispatches a release classified as a prerelease under `rc` |
| `hotfix-cycle` | `base: hotfix` cuts `hotfix/X.Y.Z+1` from the latest stable tag, leaving out `develop`'s unreleased commits, and its RC reaches approval |

Run it when no fixture release is waiting for approval: release runs share one concurrency
group, so a waiting run holds the others back.

```
python3 e2e/run.py                 # all scenarios
python3 e2e/run.py --only rc-cycle
```

## Manual checks

A GitHub App can't review deployments, so these need a person who is a `production` reviewer on
the fixture. Do them once per `v1.x` release, on runs the suite didn't cancel.

| Check | How | Expect |
| --- | --- | --- |
| Approve an RC | `prepare-release X.Y.Z-rc.N` (dry-run off), approve the release run | publish runs `npm publish --dry-run --tag rc`; a draft GitHub Release marked prerelease; no merge-back PR; Slack payload `released (dry run)` |
| Approve a stable release | `prepare-release X.Y.Z`, merge the PR, approve the release run | draft GitHub Release with grouped notes and Jira links; merge-back PR `master` → `develop` merged; `release/X.Y.Z` still exists |
| Reject | Reject any release run's deployment | tag withdrawn; Slack payload `release rejected; tag withdrawn` |
| Re-run after publish | Re-run a finished stable run | prepare's resume plan is `skip-publish`; GitHub Release and merge-back are skipped as already done |
