#!/usr/bin/env bash
# Cut or reuse the release branch, sync version files, and push. Run from the SDK repo root with
# release-tool and git-cliff on PATH.
#
#   stable X.Y.Z      regenerate the X.Y.Z CHANGELOG section; the workflow then opens the PR to master
#   RC X.Y.Z-rc.N     no CHANGELOG change; tag the commit; the workflow then dispatches release
#
# The branch is release/X.Y.Z, or hotfix/X.Y.Z when BASE=hotfix. An existing release/X.Y.Z or
# hotfix/X.Y.Z is always reused, so BASE only matters when the branch is cut.
#
#   VERSION       X.Y.Z or X.Y.Z-rc.N
#   BASE          develop (default): cut from develop; hotfix: cut from the latest stable tag
#   DRY_RUN       "true" prints the plan and the diff, then leaves the repo untouched
#   CLIFF_CONFIG  git-cliff config used when the repo has no cliff.toml of its own
#
# Writes branch=, tag= and prerelease= to $GITHUB_OUTPUT when it is set.
set -euo pipefail

: "${VERSION:?VERSION is required}"
DRY_RUN="${DRY_RUN:-true}"
BASE="${BASE:-develop}"
case "$BASE" in
  develop|hotfix) ;;
  *) echo "error: BASE must be develop or hotfix, not '${BASE}'" >&2; exit 1 ;;
esac

release-tool config validate
classification="$(release-tool classify "$VERSION")"
prerelease="$(sed -n 's/^prerelease=//p' <<<"$classification")"
tag="$(sed -n 's/^tag=//p' <<<"$classification")"
prefix="$(release-tool config get tag-prefix)"
workdir="$(release-tool config get working-directory)"
stable="${VERSION%%-*}"

start_ref="$(git symbolic-ref --quiet --short HEAD || git rev-parse HEAD)"

git fetch --quiet --tags origin
for t in "$tag" "${prefix}${stable}"; do
  if git rev-parse -q --verify "refs/tags/${t}" >/dev/null; then
    echo "error: tag ${t} already exists; ${stable} has been released or ${VERSION} already prepared" >&2
    exit 1
  fi
done

if git ls-remote --exit-code --heads origin "release/${stable}" >/dev/null; then
  branch="release/${stable}"
  echo "Reusing existing ${branch}"
  git fetch --quiet origin "$branch"
  git checkout --quiet -B "$branch" "origin/${branch}"
elif git ls-remote --exit-code --heads origin "hotfix/${stable}" >/dev/null; then
  branch="hotfix/${stable}"
  echo "Reusing existing ${branch}"
  git fetch --quiet origin "$branch"
  git checkout --quiet -B "$branch" "origin/${branch}"
elif [ "$BASE" = hotfix ]; then
  git tag --list > "${RUNNER_TEMP:-/tmp}/release-tags.txt"
  from="$(release-tool hotfix-check "$VERSION" --tags "${RUNNER_TEMP:-/tmp}/release-tags.txt")"
  branch="hotfix/${stable}"
  echo "Cutting ${branch} from ${from}"
  git checkout --quiet -B "$branch" "refs/tags/${from}"
else
  branch="release/${stable}"
  echo "Cutting ${branch} from develop"
  git fetch --quiet origin develop
  git checkout --quiet -B "$branch" origin/develop
fi

version_files=()
while IFS= read -r f; do version_files+=("$f"); done < <(release-tool version write "$VERSION")
to_commit=("${version_files[@]}")

changelog="${workdir}/CHANGELOG.md"
if [ "$prerelease" = false ]; then
  config="cliff.toml"
  [ -f "$config" ] || config="${CLIFF_CONFIG:?CLIFF_CONFIG is required when the repo has no cliff.toml}"
  touch "$changelog"  # --prepend needs an existing file
  release-tool changelog drop "$VERSION" --file "$changelog"  # regenerate, never append twice
  RELEASE_VERSION="$VERSION" \
  GIT_CLIFF__GIT__TAG_PATTERN="^${prefix}[0-9]+\.[0-9]+\.[0-9]+$" \
    git-cliff --config "$config" --unreleased --tag "${prefix}${stable}" --prepend "$changelog"
  to_commit+=("$changelog")
fi

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  { echo "branch=${branch}"; echo "tag=${tag}"; echo "prerelease=${prerelease}"; } >> "$GITHUB_OUTPUT"
fi

if [ "$DRY_RUN" = "true" ]; then
  if [ "$prerelease" = true ]; then
    echo "Dry run: would commit the following on ${branch}, tag it ${tag}, push both, and dispatch release"
  else
    echo "Dry run: would commit the following on ${branch}, push it, and open or update the PR to master"
    git add --intent-to-add -- "$changelog"  # include a new CHANGELOG in the diff
  fi
  git --no-pager diff
  git reset --quiet && git checkout --quiet -- . && git clean --quiet -fd -- "$changelog"
  git checkout --quiet "$start_ref"
  exit 0
fi

git add -- "${to_commit[@]}"
if git diff --cached --quiet; then
  echo "${branch} already has ${VERSION}; nothing to commit"
else
  git commit --quiet -m "chore(release): ${VERSION}"
fi
git push --quiet origin "$branch"
echo "Pushed ${branch}"

if [ "$prerelease" = true ]; then
  git tag "$tag"
  git push --quiet origin "refs/tags/${tag}"
  echo "Tagged ${tag}"
fi
