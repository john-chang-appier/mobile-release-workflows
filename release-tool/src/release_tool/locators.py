"""Find the version string inside a file, by yq-style path (YAML/JSON) or regex.

Both kinds return the exact character span of the value so a write replaces only that
text, keeping comments, quoting, and formatting of the rest of the file intact.
"""
import re
from pathlib import Path

import yaml


class LocatorError(Exception):
    pass


def read(repo: Path, locator: dict) -> str:
    text = _text(repo, locator)
    start, end = _span(text, locator)
    return text[start:end]


def write(repo: Path, locator: dict, value: str) -> None:
    text = _text(repo, locator)
    start, end = _span(text, locator)
    (repo / locator["file"]).write_text(text[:start] + value + text[end:])


def _text(repo: Path, locator: dict) -> str:
    path = repo / locator["file"]
    if not path.is_file():
        raise LocatorError(f"{locator['file']}: not found")
    return path.read_text()


def _span(text: str, locator: dict) -> tuple[int, int]:
    if "regex" in locator:
        match = re.search(locator["regex"], text)
        if not match:
            raise LocatorError(f"{locator['file']}: no match for regex {locator['regex']!r}")
        return match.span(1)
    return _path_span(text, locator)


def _path_span(text: str, locator: dict) -> tuple[int, int]:
    # JSON is a subset of YAML for these files, so one parser covers package.json too.
    node = yaml.compose(text)
    for key in _path_keys(locator["path"]):
        node = _child(node, key)
        if node is None:
            raise LocatorError(f"{locator['file']}: path {locator['path']!r} not found")
    if not isinstance(node, yaml.ScalarNode):
        raise LocatorError(f"{locator['file']}: path {locator['path']!r} is not a scalar")
    start, end = node.start_mark.index, node.end_mark.index
    if node.style in ("'", '"'):
        start, end = start + 1, end - 1
    return start, end


def _path_keys(path: str) -> list:
    keys = []
    for part in re.findall(r"\.([^.\[\]]+)|\[(\d+)\]", path):
        keys.append(part[0] if part[0] else int(part[1]))
    return keys


def _child(node, key):
    if isinstance(key, int):
        if isinstance(node, yaml.SequenceNode) and key < len(node.value):
            return node.value[key]
        return None
    if isinstance(node, yaml.MappingNode):
        for k, v in node.value:
            if k.value == key:
                return v
    return None
