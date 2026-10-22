import pytest


@pytest.mark.parametrize(
    "tag_exists, published, expected",
    [
        ("true", "false", "publish"),
        ("true", "true", "skip-publish"),
        ("false", "true", "fail"),
        ("false", "false", "fail"),
    ],
)
def test_plan_follows_the_resume_table(run, tag_exists, published, expected):
    code, out, _ = run("plan", "--tag-exists", tag_exists, "--published", published)
    assert out == f"{expected}\n"
    assert code == 0
