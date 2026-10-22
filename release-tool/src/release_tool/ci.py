"""Decide whether CI passed on a commit, from GitHub's workflow runs and commit statuses."""
import json
from dataclasses import dataclass, field
from pathlib import Path

PASSED = ("success", "skipped", "neutral")


@dataclass
class Verdict:
    failed: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)


def verdict(runs_file: Path, statuses_file: Path, exclude_path: str) -> Verdict:
    runs = _latest_per_workflow(json.loads(runs_file.read_text())["workflow_runs"], exclude_path)
    statuses = json.loads(statuses_file.read_text())["statuses"]
    v = Verdict()
    if not runs and not statuses:
        v.pending.append("no CI has started on this commit")
    for r in runs:
        if r["status"] != "completed":
            v.pending.append(f"{r['name']}: {r['status']}")
        elif r["conclusion"] not in PASSED:
            v.failed.append(f"{r['name']}: {r['conclusion']}")
    for s in statuses:
        if s["state"] == "pending":
            v.pending.append(f"{s['context']}: pending")
        elif s["state"] != "success":
            v.failed.append(f"{s['context']}: {s['state']}")
    return v


def _latest_per_workflow(runs: list[dict], exclude_path: str) -> list[dict]:
    # A re-triggered workflow leaves its earlier runs behind; only the newest one counts.
    latest = {}
    for r in sorted(runs, key=lambda r: r["id"]):
        if r["path"] != exclude_path:
            latest[r["path"]] = r
    return list(latest.values())
