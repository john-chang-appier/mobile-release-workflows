import re
from pathlib import Path

import yaml

CONFIG_FILE = ".github/release-config.yml"
PLATFORMS = ("flutter", "react-native", "android", "ios")
DEFAULTS = {"working-directory": ".", "tag-prefix": "v", "channels": ["public"]}


class ConfigError(Exception):
    pass


def load(repo: Path) -> dict:
    path = repo / CONFIG_FILE
    if not path.is_file():
        raise ConfigError(f"{CONFIG_FILE}: not found")
    data = yaml.safe_load(path.read_text()) or {}
    _validate(data)
    return {**DEFAULTS, **data}


def _validate(data: dict) -> None:
    if "platform" not in data:
        raise ConfigError("platform: required")
    if data["platform"] not in PLATFORMS:
        raise ConfigError(f"platform: unknown value {data['platform']!r}, expected one of {', '.join(PLATFORMS)}")
    for field, locator in locators(data):
        _validate_locator(field, locator)


def locators(data: dict):
    """Yield (field name, locator) for the primary version file, then each sync file."""
    version = data.get("version") or {}
    yield "version.primary", version.get("primary")
    for i, locator in enumerate(version.get("sync") or []):
        yield f"version.sync[{i}]", locator


def _validate_locator(field: str, locator) -> None:
    if not isinstance(locator, dict) or "file" not in locator:
        raise ConfigError(f"{field}: required, with a 'file' and either 'path' or 'regex'")
    if ("path" in locator) == ("regex" in locator):
        raise ConfigError(f"{field}: needs exactly one of 'path' or 'regex'")
    if "regex" in locator:
        try:
            groups = re.compile(locator["regex"]).groups
        except re.error as e:
            raise ConfigError(f"{field}: invalid regex: {e}") from None
        if groups != 1:
            raise ConfigError(f"{field}: regex must have exactly one capture group, found {groups}")
