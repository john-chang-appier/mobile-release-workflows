#!/usr/bin/env bash
# Release this repo: run the Seam 2 suite against main, then tag vX.Y.Z and move the major tag.
#
#   scripts/release-central.sh 1.0.0
set -euo pipefail

version="${1:?usage: release-central.sh X.Y.Z}"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "error: $version is not X.Y.Z" >&2; exit 1; }
major="v${version%%.*}"

git fetch --quiet origin main --tags
sha="$(git rev-parse origin/main)"
[ "$(git rev-parse HEAD)" = "$sha" ] || { echo "error: check out origin/main ($sha) first" >&2; exit 1; }
git rev-parse -q --verify "refs/tags/v${version}" >/dev/null && { echo "error: v${version} exists" >&2; exit 1; }

(cd release-tool && python3 -m pytest -q)
python3 e2e/run.py

git fetch --quiet origin main
[ "$(git rev-parse origin/main)" = "$sha" ] || { echo "error: main moved during the suite; run again" >&2; exit 1; }

git tag -a "v${version}" -m "v${version}" "$sha"
git tag -f -a "$major" -m "$major → v${version}" "$sha"
git push origin "v${version}"
git push --force origin "$major"
echo "Released v${version}; ${major} now points at ${sha}"
