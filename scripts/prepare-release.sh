#!/usr/bin/env bash
# Cut or reuse release/<version>, sync version files, prepend the CHANGELOG section, and
# push. Run from the SDK repo root with release-tool and git-cliff on PATH.
#
#   VERSION       stable version, X.Y.Z
#   DRY_RUN       "true" prints the plan and the diff, then leaves the repo untouched
#   CLIFF_CONFIG  git-cliff config used when the repo has no cliff.toml of its own
set -euo pipefail

: "${VERSION:?VERSION is required}"
DRY_RUN="${DRY_RUN:-true}"

release-tool config validate
case "$VERSION" in
  *-*) echo "error: $VERSION is a prerelease; RC releases are not supported yet" >&2; exit 1 ;;
esac

prefix="$(release-tool config get tag-prefix)"
workdir="$(release-tool config get working-directory)"
tag="${prefix}${VERSION}"
branch="release/${VERSION}"

git fetch --quiet --tags origin
if git rev-parse -q --verify "refs/tags/${tag}" >/dev/null; then
  echo "error: tag ${tag} already exists; ${VERSION} has been released" >&2
  exit 1
fi

if git ls-remote --exit-code --heads origin "$branch" >/dev/null; then
  echo "Reusing existing ${branch}"
  git fetch --quiet origin "$branch"
  git checkout --quiet -B "$branch" "origin/${branch}"
else
  echo "Cutting ${branch} from develop"
  git fetch --quiet origin develop
  git checkout --quiet -B "$branch" origin/develop
fi

release-tool version write "$VERSION"

changelog="${workdir}/CHANGELOG.md"
config="cliff.toml"
[ -f "$config" ] || config="${CLIFF_CONFIG:?CLIFF_CONFIG is required when the repo has no cliff.toml}"
if [ -f "$changelog" ] && grep -q "^## \[${VERSION}\]" "$changelog"; then
  echo "${changelog} already has a ${VERSION} section; leaving it as is"
else
  touch "$changelog"  # --prepend needs an existing file
  git-cliff --config "$config" --unreleased --tag "$tag" --prepend "$changelog"
fi

if [ "$DRY_RUN" = "true" ]; then
  echo "Dry run: would commit the following on ${branch}, push it, and open a PR to master"
  git add --intent-to-add -- "$changelog"  # include the new CHANGELOG in the diff
  git --no-pager diff
  git reset --quiet && git checkout --quiet -- . && git clean --quiet -fd -- "$changelog"
  exit 0
fi

git add -A
if git diff --cached --quiet; then
  echo "${branch} already has ${VERSION} and its CHANGELOG section; nothing to commit"
else
  git commit --quiet -m "chore(release): ${VERSION}"
fi
git push --quiet origin "$branch"
echo "Pushed ${branch}"
