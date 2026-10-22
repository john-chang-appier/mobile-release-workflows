import pytest

from conftest import edit_config


@pytest.mark.parametrize(
    "layout, tag",
    [("flutter", "v3.7.0"), ("react-native", "v2.3.1"), ("android", "v8.11.0")],
)
def test_verify_passes_when_every_file_matches_the_tag(repo, run, layout, tag):
    code, _, _ = run("version", "verify", tag, "--repo", repo(layout))
    assert code == 0


def test_verify_lists_every_mismatched_file(repo, run):
    r = repo("flutter")

    code, _, err = run("version", "verify", "v3.8.0", "--repo", r)

    assert code != 0
    for f in [
        "sdk/pubspec.yaml",
        "sdk/package.json",
        "sdk/android/build.gradle",
        "sdk/ios/appier_flutter.podspec",
    ]:
        assert f"{f} " in err
    assert "3.7.0, expected 3.8.0" in err


def test_verify_honours_a_custom_tag_prefix(repo, run):
    r = repo("android")
    edit_config(r, lambda c: c.update({"tag-prefix": "release-"}))

    assert run("version", "verify", "release-8.11.0", "--repo", r)[0] == 0
    assert run("version", "verify", "v8.11.0", "--repo", r)[0] != 0


@pytest.mark.parametrize("layout", ["flutter", "react-native", "android"])
def test_write_makes_every_file_agree_with_the_new_version(repo, run, layout):
    r = repo(layout)

    assert run("version", "write", "9.0.0", "--repo", r)[0] == 0

    assert run("version", "verify", "v9.0.0", "--repo", r)[0] == 0


def test_write_changes_only_the_version_values(repo, run):
    r = repo("flutter")

    run("version", "write", "3.8.0", "--repo", r)

    assert (r / "sdk/android/build.gradle").read_text() == (
        "group 'com.appier.appier_flutter'\n"
        "version '1.0-SNAPSHOT'\n"
        "\n"
        "buildscript {\n"
        "    ext.kotlin_version = '1.8.22'\n"
        "    ext.appier_version = '8.11.0'\n"
        "    ext.appier_sub_version = '3.8.0'\n"
        "}\n"
    )
    assert (r / "sdk/ios/appier_flutter.podspec").read_text() == (
        "Pod::Spec.new do |s|\n"
        "  s.name             = 'appier_flutter'\n"
        "  s.version          = '3.8.0'\n"
        "  s.dependency 'AppierFramework', '8.11.3'\n"
        "end\n"
    )
    assert (r / "sdk/package.json").read_text() == (
        "{\n"
        '  "name": "appier_flutter",\n'
        '  "version": "3.8.0",\n'
        '  "private": true\n'
        "}\n"
    )
    pubspec = (r / "sdk/pubspec.yaml").read_text()
    assert "version: 3.8.0\n" in pubspec
    assert "  # keep in sync with .fvmrc\n" in pubspec


def test_write_turns_an_rc_back_into_the_stable_version(repo, run):
    r = repo("react-native")
    run("version", "write", "2.4.0-rc.2", "--repo", r)

    run("version", "write", "2.4.0", "--repo", r)

    assert '"version": "2.4.0",' in (r / "package.json").read_text()


def test_write_rejects_a_malformed_version(repo, run):
    r = repo("react-native")

    code, _, err = run("version", "write", "2.4", "--repo", r)

    assert code != 0
    assert "2.4" in err
    assert '"version": "2.3.1",' in (r / "package.json").read_text()
