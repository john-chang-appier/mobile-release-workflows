# Release runbook

What to do when a release goes wrong. The pipeline itself never rolls back; every step below is
manual.

## A release run failed or is stuck

| Situation | What the pipeline already did | What you do |
| --- | --- | --- |
| Failed before publish (version mismatch, CI red, build or verify error) | Withdrew the tag; Slack says `release failed` | Fix it on `release/X.Y.Z` (or `hotfix/X.Y.Z`), then merge a new release PR. For a transient error (registry or network), re-run the **tag-on-merge** run of the merged PR instead: it re-creates the tag and dispatches a fresh release |
| `prepare` waits for CI and times out | Withdrew the tag | Get CI green on the merge commit, then re-run the tag-on-merge run |
| Failed after publish (GitHub Release, merge-back, Slack) | Kept the tag, because the registry has the version | **Re-run failed jobs** on the release run. The resume plan is `skip-publish`, so nothing is published twice |
| Waiting for approval, but it shouldn't ship | — | **Reject** the deployment. The tag is withdrawn and Slack says `release rejected` |
| Merge-back PR has conflicts | Opened the PR; Slack links it | Resolve the conflicts on the PR and merge it the same day |
| A version was published by hand, outside the pipeline | — | A release run on its tag sees the version in the registry and skips publish, so the pipeline never checks that artifact. Compare the registry artifact with the tag before letting the run finish, or reject it and ship the next patch |

To find the tag-on-merge run: Actions → **tag-on-merge** → the run for the merged
`release/X.Y.Z` PR → **Re-run all jobs**.

## A bad version reached users

No registry lets a version number be reused. The fix is always a new version, usually through a
hotfix (`prepare-release` with `base: hotfix`). Do the registry step first, so fewer apps pick up
the bad version while the hotfix is prepared.

### npm (`@appier/react-native-sdk`)

Needs an npm account with publish rights on the package; OIDC trusted publishing only works
inside the release workflow.

```sh
# Warn everyone who installs it
npm deprecate @appier/react-native-sdk@2.4.0 "2.4.0 crashes on Android 14; use 2.4.1"

# If it was published as latest, point latest back at the last good version
npm dist-tag add @appier/react-native-sdk@2.3.1 latest

# Only within 72 hours of publishing, and only if nothing depends on it.
# The version number can never be published again.
npm unpublish @appier/react-native-sdk@2.4.0
```

Undo a deprecation with `npm deprecate @appier/react-native-sdk@2.4.0 ""`.

### GitHub Packages (`internal` channel)

```sh
# Find the version id
gh api /orgs/plaxieappier/packages/npm/react-native-sdk/versions --jq '.[] | "\(.id) \(.name)"'
# Delete it
gh api -X DELETE /orgs/plaxieappier/packages/npm/react-native-sdk/versions/<id>
```

### pub.dev (`appier_flutter`)

Retract the version in the browser: pub.dev → `appier_flutter` → **Admin** → **Versions** →
**Retract** next to the version. Retraction is possible within 7 days of publishing and can be
undone in the same place. A retracted version stays downloadable for apps that already lock it,
but new resolves skip it. After 7 days, only a new patch version helps.

### Maven Central (`appier-android`)

Published components can't be removed or replaced. Publish the next patch through a hotfix and
announce it. A deployment that has not been published yet can still be dropped in the Central
Portal under **Deployments** → **Drop**.

## After any of the above

- Post in the release channel what happened and which version replaces the bad one.
- If the cause was in this repo's workflows, add a Seam 2 scenario that would have caught it.
