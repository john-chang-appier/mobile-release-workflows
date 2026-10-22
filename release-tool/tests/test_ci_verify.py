import json

RELEASE = ".github/workflows/release.yml"


def write_json(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


def run_(name, path, status="completed", conclusion="success", run_id=1):
    return {"id": run_id, "name": name, "path": path, "status": status, "conclusion": conclusion}


def verify(run, tmp_path, runs, statuses=None):
    runs_file = write_json(tmp_path, "runs.json", {"workflow_runs": runs})
    status_file = write_json(
        tmp_path, "status.json", statuses or {"state": "pending", "total_count": 0, "statuses": []}
    )
    return run("ci", "verify", "--runs", runs_file, "--statuses", status_file, "--exclude-path", RELEASE)


def test_passes_when_every_ci_run_succeeded(run, tmp_path):
    code, _, _ = verify(run, tmp_path, [run_("ci", ".github/workflows/ci.yml")])
    assert code == 0


def test_fails_naming_each_failed_run(run, tmp_path):
    code, _, err = verify(
        run,
        tmp_path,
        [
            run_("ci", ".github/workflows/ci.yml", conclusion="failure", run_id=1),
            run_("lint", ".github/workflows/lint.yml", conclusion="success", run_id=2),
            run_("ios-build", ".github/workflows/ios.yml", conclusion="cancelled", run_id=3),
        ],
    )

    assert code == 1
    assert "ci: failure" in err
    assert "ios-build: cancelled" in err
    assert "lint" not in err


def test_ignores_the_release_workflow_itself(run, tmp_path):
    code, _, _ = verify(
        run,
        tmp_path,
        [
            run_("ci", ".github/workflows/ci.yml", run_id=1),
            run_("release", RELEASE, status="in_progress", conclusion=None, run_id=2),
            run_("release", RELEASE, conclusion="failure", run_id=3),
        ],
    )
    assert code == 0


PENDING = 2


def test_reports_pending_while_ci_is_still_running(run, tmp_path):
    code, _, err = verify(
        run, tmp_path, [run_("ci", ".github/workflows/ci.yml", status="in_progress", conclusion=None)]
    )
    assert code == PENDING
    assert "ci: in_progress" in err


def test_reports_pending_when_no_ci_has_started_on_the_commit(run, tmp_path):
    code, _, err = verify(run, tmp_path, [run_("release", RELEASE)])
    assert code == PENDING
    assert "no CI" in err


def test_reports_pending_for_a_pending_commit_status(run, tmp_path):
    code, _, _ = verify(
        run,
        tmp_path,
        [run_("ci", ".github/workflows/ci.yml")],
        {"state": "pending", "total_count": 1, "statuses": [{"context": "bitrise/ios", "state": "pending"}]},
    )
    assert code == PENDING


def test_a_failure_outranks_a_run_still_in_progress(run, tmp_path):
    code, _, _ = verify(
        run,
        tmp_path,
        [
            run_("ci", ".github/workflows/ci.yml", conclusion="failure", run_id=1),
            run_("ios", ".github/workflows/ios.yml", status="in_progress", conclusion=None, run_id=2),
        ],
    )
    assert code == 1


def test_only_the_latest_run_of_each_workflow_counts(run, tmp_path):
    # A failed CI run followed by a fresh successful run of the same workflow.
    code, _, _ = verify(
        run,
        tmp_path,
        [
            run_("ci", ".github/workflows/ci.yml", conclusion="success", run_id=7),
            run_("ci", ".github/workflows/ci.yml", conclusion="failure", run_id=5),
        ],
    )
    assert code == 0


def test_fails_on_a_failing_commit_status(run, tmp_path):
    code, _, err = verify(
        run,
        tmp_path,
        [run_("ci", ".github/workflows/ci.yml")],
        {
            "state": "failure",
            "total_count": 2,
            "statuses": [
                {"context": "bitrise/ios", "state": "failure"},
                {"context": "codecov", "state": "success"},
            ],
        },
    )
    assert code == 1
    assert "bitrise/ios: failure" in err
    assert "codecov" not in err


def test_commit_statuses_alone_count_as_ci(run, tmp_path):
    code, _, _ = verify(
        run,
        tmp_path,
        [],
        {"state": "success", "total_count": 1, "statuses": [{"context": "bitrise/ios", "state": "success"}]},
    )
    assert code == 0
