import json

import pytest

BASE = ["--repo-name", "plaxieappier/appier_flutter", "--version", "3.8.0", "--run-url", "https://run/1"]


def message(run, *extra):
    code, out, _ = run("slack-message", *BASE, *extra)
    assert code == 0
    return json.loads(out)["text"]


def test_success_names_the_version_and_links_the_artifact(run):
    text = message(run, "--outcome", "success", "--artifact-url", "https://pub.dev/packages/appier_flutter/versions/3.8.0")
    assert text.splitlines()[0] == ":white_check_mark: plaxieappier/appier_flutter 3.8.0 released"
    assert "https://pub.dev/packages/appier_flutter/versions/3.8.0" in text
    assert "https://run/1" in text


@pytest.mark.parametrize(
    "outcome, first_line",
    [
        ("failure", ":x: plaxieappier/appier_flutter 3.8.0 release failed"),
        ("rejected", ":no_entry: plaxieappier/appier_flutter 3.8.0 release rejected; tag withdrawn"),
    ],
)
def test_failure_and_rejection_each_get_their_own_message(run, outcome, first_line):
    assert message(run, "--outcome", outcome).splitlines()[0] == first_line


def test_includes_drift_warnings_and_a_merge_back_conflict(run, tmp_path):
    warnings = tmp_path / "drift.txt"
    warnings.write_text("AppierFramework pins 8.11.2; appier/appier-ios-framework is at 8.11.3\n")

    text = message(
        run,
        "--outcome", "success",
        "--warnings", warnings,
        "--merge-back-conflict", "https://github.com/x/y/pull/9",
    )

    assert ":warning: AppierFramework pins 8.11.2; appier/appier-ios-framework is at 8.11.3" in text
    assert ":warning: merge-back to develop has conflicts: https://github.com/x/y/pull/9" in text


def test_dry_run_is_marked(run):
    assert message(run, "--outcome", "success", "--dry-run").splitlines()[0].endswith("(dry run)")
