import pytest

TAGS = ["v1.0.0", "v1.1.0", "v1.2.0-rc.1", "v1.2.0", "v1.3.0-rc.1", "v0.9.0", "nightly"]


def check(run, repo, tmp_path, version, tags=TAGS):
    tags_file = tmp_path / "tags.txt"
    tags_file.write_text("\n".join(tags) + "\n")
    return run("hotfix-check", version, "--tags", tags_file, "--repo", repo("react-native"))


def test_accepts_the_patch_after_the_latest_stable_and_prints_its_tag(run, repo, tmp_path):
    code, out, _ = check(run, repo, tmp_path, "1.2.1")
    assert code == 0
    assert out == "v1.2.0\n"


def test_accepts_an_rc_of_that_patch(run, repo, tmp_path):
    assert check(run, repo, tmp_path, "1.2.1-rc.1")[:2] == (0, "v1.2.0\n")


@pytest.mark.parametrize("version", ["1.2.2", "1.3.0", "1.1.5", "1.2.2-rc.1"])
def test_rejects_anything_else(run, repo, tmp_path, version):
    code, out, err = check(run, repo, tmp_path, version)
    assert code == 1
    assert out == ""
    assert "1.2.1" in err


def test_fails_when_nothing_stable_was_released(run, repo, tmp_path):
    code, _, err = check(run, repo, tmp_path, "0.0.1", tags=["v0.1.0-rc.1"])
    assert code == 1
    assert "no stable" in err
