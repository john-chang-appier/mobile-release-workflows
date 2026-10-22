"""The one Slack message a release run posts, whatever its outcome."""

HEADLINES = {
    "success": ":white_check_mark: {repo} {version} released",
    "failure": ":x: {repo} {version} release failed",
    "rejected": ":no_entry: {repo} {version} release rejected; tag withdrawn",
}


def message(outcome, repo, version, run_url, artifact_url=None, warnings=(), conflict_url=None, dry_run=False):
    headline = HEADLINES[outcome].format(repo=repo, version=version)
    lines = [headline + (" (dry run)" if dry_run else "")]
    if artifact_url:
        lines.append(artifact_url)
    lines += [f":warning: {w}" for w in warnings]
    if conflict_url:
        lines.append(f":warning: merge-back to develop has conflicts: {conflict_url}")
    lines.append(f"Run: {run_url}")
    return {"text": "\n".join(lines)}
