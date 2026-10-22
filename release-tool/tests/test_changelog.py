CHANGELOG = """\
## [1.2.0] - 2026-10-20

### Features

- Old entry

## [1.1.0] - 2026-09-01

### Bug Fixes

- Earlier fix
"""


def test_drop_removes_only_that_versions_section(run, tmp_path):
    f = tmp_path / "CHANGELOG.md"
    f.write_text(CHANGELOG)

    code, _, _ = run("changelog", "drop", "1.2.0", "--file", f)

    assert code == 0
    assert f.read_text() == "## [1.1.0] - 2026-09-01\n\n### Bug Fixes\n\n- Earlier fix\n"


def test_drop_leaves_the_file_alone_when_the_version_is_absent(run, tmp_path):
    f = tmp_path / "CHANGELOG.md"
    f.write_text(CHANGELOG)

    assert run("changelog", "drop", "1.3.0", "--file", f)[0] == 0
    assert f.read_text() == CHANGELOG


def test_drop_does_not_match_a_longer_version(run, tmp_path):
    f = tmp_path / "CHANGELOG.md"
    f.write_text("## [1.2.0-rc.1] - x\n\n- rc\n\n## [11.2.0] - y\n\n- other\n")

    run("changelog", "drop", "1.2.0", "--file", f)

    assert f.read_text() == "## [1.2.0-rc.1] - x\n\n- rc\n\n## [11.2.0] - y\n\n- other\n"
