# mobile-release-workflows

The shared release pipeline for Appier mobile SDKs. Design: MT-9607 proposal in
`plaxieappier/sdk-dev-docs` (`products/appier-one-sdk/proposals/2026-10-21-MT-9607_shared-release-workflow.md`).

| Path | What it is |
| --- | --- |
| `.github/workflows/prepare-release.yml` | Reusable workflow: cut or reuse `release/X.Y.Z`, sync version files, prepend the CHANGELOG section, open the PR to `master` |
| `release-tool/` | Python CLI holding the release decision logic; the unit-test seam |
| `scripts/prepare-release.sh` | Git steps of `prepare-release`, runnable locally against any remote |
| `cliff.toml` | Default git-cliff config: conventional-commit groups and Jira links. A repo's own `cliff.toml` wins |

## Using it from an SDK repo

1. Add `.github/release-config.yml`:

   ```yaml
   platform: flutter            # flutter | react-native | android | ios
   working-directory: sdk       # default "."; CHANGELOG.md lives here
   tag-prefix: v                # default "v"
   version:
     primary: {file: sdk/pubspec.yaml, path: .version}
     sync:
       - {file: sdk/android/build.gradle, regex: "ext\\.appier_sub_version = '([^']+)'"}
   ```

   A locator is `{file, path}` (yq-style path into YAML or JSON) or `{file, regex}` with exactly
   one capture group. `file` is relative to the repo root.

2. Add a caller workflow that `uses: plaxieappier/mobile-release-workflows/.github/workflows/prepare-release.yml@v1`
   with `version` and `dry-run` inputs (manual dispatches should default `dry-run` to `true`).

## release-tool

```
release-tool config validate              # exit 1 naming the offending field
release-tool config get <key>             # platform | working-directory | tag-prefix
release-tool version write <X.Y.Z[-rc.N]> # rewrite every version file
release-tool version verify <tag>         # exit 1 listing every file that disagrees
```

All commands take `--repo <dir>` (default `.`).

## Development

```
python3 -m venv .venv && .venv/bin/pip install -e 'release-tool[test]' git-cliff
.venv/bin/pytest -q release-tool
```
