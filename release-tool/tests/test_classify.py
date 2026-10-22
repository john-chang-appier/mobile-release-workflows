import pytest

from conftest import edit_config


def test_stable_version_is_latest_and_not_a_prerelease(repo, run):
    code, out, _ = run("classify", "1.2.3", "--repo", repo("react-native"))
    assert code == 0
    assert out == "prerelease=false\ndist-tag=latest\ntag=v1.2.3\n"


def test_release_candidate_is_a_prerelease_under_rc(repo, run):
    code, out, _ = run("classify", "1.2.3-rc.1", "--repo", repo("react-native"))
    assert code == 0
    assert out == "prerelease=true\ndist-tag=rc\ntag=v1.2.3-rc.1\n"


def test_tag_uses_the_configured_prefix(repo, run):
    r = repo("android")
    edit_config(r, lambda c: c.update({"tag-prefix": "release-"}))
    assert "tag=release-8.12.0\n" in run("classify", "8.12.0", "--repo", r)[1]


@pytest.mark.parametrize("bad", ["1.2", "1.2.3-beta.1", "v1.2.3", "1.2.3-rc.0"])
def test_malformed_version_is_rejected(repo, run, bad):
    code, out, err = run("classify", bad, "--repo", repo("react-native"))
    assert code == 1
    assert out == ""
    assert bad in err
