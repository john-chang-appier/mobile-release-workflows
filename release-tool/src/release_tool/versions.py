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
