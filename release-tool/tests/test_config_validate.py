import pytest

from conftest import edit_config


@pytest.mark.parametrize("layout", ["flutter", "react-native", "android"])
def test_real_layouts_are_valid(repo, run, layout):
    code, _, _ = run("config", "validate", "--repo", repo(layout))
    assert code == 0


def test_missing_platform_is_rejected(repo, run):
    r = repo("react-native")
    edit_config(r, lambda c: c.pop("platform"))

    code, _, err = run("config", "validate", "--repo", r)

    assert code != 0
    assert "platform" in err


def test_unknown_platform_is_rejected(repo, run):
    r = repo("react-native")
    edit_config(r, lambda c: c.update(platform="windows"))

    code, _, err = run("config", "validate", "--repo", r)

    assert code != 0
    assert "platform" in err and "windows" in err


def test_regex_locator_without_capture_group_is_rejected(repo, run):
    r = repo("android")
    edit_config(r, lambda c: c["version"]["primary"].update(regex="(?m)^version=.+$"))

    code, _, err = run("config", "validate", "--repo", r)

    assert code != 0
    assert "version.primary" in err and "capture group" in err


def test_get_returns_defaults_for_optional_fields(repo, run):
    r = repo("react-native")

    assert run("config", "get", "tag-prefix", "--repo", r)[1] == "v\n"
    assert run("config", "get", "working-directory", "--repo", r)[1] == ".\n"


def test_get_returns_the_configured_value(repo, run):
    assert run("config", "get", "working-directory", "--repo", repo("flutter"))[1] == "sdk\n"
