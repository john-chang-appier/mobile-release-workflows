import re
from pathlib import Path

from . import config, locators


# Stable X.Y.Z or release candidate X.Y.Z-rc.N; nothing else is released by the pipeline.
VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-rc\.[1-9]\d*)?")


class VersionError(Exception):
    pass


def check(version: str) -> None:
    if not VERSION.fullmatch(version):
        raise VersionError(f"{version!r} is not a release version (X.Y.Z or X.Y.Z-rc.N)")


def is_prerelease(version: str) -> bool:
    return VERSION.fullmatch(version).group(4) is not None


def version_from_tag(data: dict, tag: str) -> str:
    prefix = data["tag-prefix"]
    if not tag.startswith(prefix):
        raise VersionError(f"tag {tag!r} does not start with tag-prefix {prefix!r}")
    return tag[len(prefix):]


def mismatches(repo: Path, data: dict, version: str) -> list[str]:
    """Return one line per version file whose value differs from `version`."""
    lines = []
    for field, locator in config.locators(data):
        found = locators.read(repo, locator)
        if found != version:
            lines.append(f"{locator['file']} ({field}): {found}, expected {version}")
    return lines


def write(repo: Path, data: dict, version: str) -> list[str]:
    """Write `version` into every version file; return the files changed."""
    check(version)
    targets = [locator for _, locator in config.locators(data)]
    for locator in targets:  # fail before touching any file if one can't be located
        locators.read(repo, locator)
    for locator in targets:
        locators.write(repo, locator, version)
    return [locator["file"] for locator in targets]


def stable_triple(version: str) -> tuple[int, int, int]:
    match = VERSION.fullmatch(version)
    return tuple(int(match.group(i)) for i in (1, 2, 3))


def latest_stable_tag(data: dict, tags: list[str]) -> str:
    """The highest X.Y.Z tag (with the repo's tag-prefix); prereleases and other tags are ignored."""
    prefix = data["tag-prefix"]
    stable = []
    for tag in tags:
        version = tag[len(prefix):] if tag.startswith(prefix) else None
        if version and VERSION.fullmatch(version) and not is_prerelease(version):
            stable.append((stable_triple(version), tag))
    if not stable:
        raise VersionError("no stable release tag found; a hotfix needs a released version to fix")
    return max(stable)[1]


def check_hotfix(data: dict, version: str, tags: list[str]) -> str:
    """Return the latest stable tag if `version` is its next patch; raise otherwise."""
    check(version)
    base = latest_stable_tag(data, tags)
    major, minor, patch = stable_triple(base[len(data["tag-prefix"]):])
    expected = f"{major}.{minor}.{patch + 1}"
    if stable_triple(version) != (major, minor, patch + 1):
        raise VersionError(f"hotfix version {version} must be {expected} (the patch after {base})")
    return base
