import re
from pathlib import Path


def drop(path: Path, version: str) -> None:
    """Remove the `## [version]` section, so a regenerated one can replace it."""
    text = path.read_text()
    heading = re.compile(rf"^## \[{re.escape(version)}\].*$\n?", re.M)
    match = heading.search(text)
    if not match:
        return
    following = re.compile(r"^## \[", re.M).search(text, match.end())
    end = following.start() if following else len(text)
    path.write_text(text[: match.start()] + text[end:])
