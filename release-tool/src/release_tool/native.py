"""Warn when a wrapper pins a native SDK older than the native repo's latest stable tag."""
import re
from pathlib import Path

from . import locators

NUMBERS = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
STABLE_TAG = re.compile(r"^\D*(\d+)\.(\d+)\.(\d+)$")


def repos(data: dict) -> list[str]:
    return list(dict.fromkeys(dep["repo"] for dep in data.get("native-deps") or []))


def warnings(repo: Path, data: dict, tags_dir: Path) -> list[str]:
    """One line per pin behind its repo's latest stable tag, or that couldn't be compared."""
    lines = []
    for dep in data.get("native-deps") or []:
        latest = _latest(tags_dir / (dep["repo"].replace("/", "__") + ".txt"))
        if latest is None:
            lines.append(f"{dep['name']}: no tags found for {dep['repo']}")
            continue
        try:
            pinned = locators.read(repo, dep)
        except locators.LocatorError as e:
            lines.append(f"{dep['name']}: {e}")
            continue
        match = NUMBERS.search(pinned)
        if not match:
            lines.append(f"{dep['name']}: can't read a version from {pinned!r}")
        elif _triple(match) < latest[0]:
            lines.append(f"{dep['name']} pins {pinned}; {dep['repo']} is at {latest[1]}")
    return lines


def _latest(tags_file: Path):
    if not tags_file.is_file():
        return None
    stable = []
    for tag in tags_file.read_text().split():
        match = STABLE_TAG.match(tag)
        if match:
            stable.append((_triple(match), tag.lstrip("v")))
    return max(stable) if stable else None


def _triple(match) -> tuple[int, int, int]:
    return tuple(int(g or 0) for g in match.groups())
