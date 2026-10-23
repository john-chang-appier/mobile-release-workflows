#!/usr/bin/env python3
"""Seam 2: drive the fixture repo through the release pipeline and check what a release engineer
would see. Runs with the caller's `gh` login against the fixture's `main`-pinned callers.

Every scenario stops at the production approval: a GitHub App can't review deployments, so
approving and rejecting are the manual checks listed in e2e/README.md. A scenario that reaches
approval cancels the run, which must withdraw the tag.

    python3 e2e/run.py [--fixture OWNER/REPO] [--only NAME ...]
"""
import argparse
import base64
import calendar
import json
import subprocess
import sys
import time

FIXTURE = "john-chang-appier/mobile-release-fixture"
POLL = 10


class Failed(Exception):
    pass


def gh(*args, check=True):
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and result.returncode:
        raise Failed(f"gh {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def api(path, *args, check=True):
    out = gh("api", path, *args, check=check)
    return json.loads(out) if out else None


def wait(what, condition, timeout=1200):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(POLL)
    raise Failed(f"timed out waiting for {what}")


def expect(ok, message):
    if not ok:
        raise Failed(message)
    print(f"  ✓ {message}")


class Fixture:
    def __init__(self, repo):
        self.repo = repo

    def dispatch(self, workflow, ref, **inputs):
        since = time.time() - 5
        fields = [x for k, v in inputs.items() for x in ("-f", f"{k}={v}")]
        gh("workflow", "run", workflow, "-R", self.repo, "--ref", ref, *fields)
        return self.next_run(workflow, ref, since)

    def next_run(self, workflow, branch, since):
        """The first run of `workflow` on `branch` created after `since`."""

        def find():
            runs = api(f"repos/{self.repo}/actions/workflows/{workflow}/runs?branch={branch}&per_page=10")
            for run in runs["workflow_runs"]:
                if created_at(run) >= since:
                    return run["id"]
            return None

        return wait(f"a {workflow} run on {branch}", find, timeout=300)

    def run(self, run_id):
        return api(f"repos/{self.repo}/actions/runs/{run_id}")

    def jobs(self, run_id):
        jobs = api(f"repos/{self.repo}/actions/runs/{run_id}/jobs?per_page=100")["jobs"]
        return {j["name"].split(" / ")[-1]: j for j in jobs}

    def finish(self, run_id, timeout=1800):
        return wait(f"run {run_id} to finish", lambda: self._done(run_id), timeout)

    def _done(self, run_id):
        run = self.run(run_id)
        return run if run["status"] == "completed" else None

    def until_approval(self, run_id):
        """Wait until the run's publish job asks for production approval."""

        def pending():
            if self.run(run_id)["status"] == "completed":
                raise Failed(f"run {run_id} completed before asking for approval")
            return api(f"repos/{self.repo}/actions/runs/{run_id}/pending_deployments") or None

        return wait(f"run {run_id} to ask for approval", pending, timeout=2400)

    def cancel(self, run_id):
        gh("run", "cancel", str(run_id), "-R", self.repo)
        return self.finish(run_id)

    def log(self, run_id):
        """The run's log; GitHub serves it only once the run has completed."""
        return gh("run", "view", str(run_id), "-R", self.repo, "--log", check=False)

    def approval_then_cancel(self, run_id):
        """Wait for the approval request, then cancel the run; return its jobs.

        Cancels on any failure too, so a broken scenario never leaves a run holding the
        fixture's release concurrency group."""
        try:
            self.until_approval(run_id)
            return self.jobs(run_id)
        finally:
            if self.run(run_id)["status"] != "completed":
                self.cancel(run_id)

    def tag_sha(self, tag):
        ref = api(f"repos/{self.repo}/git/ref/tags/{tag}", check=False)
        return ref["object"]["sha"] if ref and "object" in ref else None

    def tags(self):
        return gh("api", "--paginate", f"repos/{self.repo}/tags?per_page=100", "--jq", ".[].name").split()

    def file(self, path, ref):
        return gh("api", f"repos/{self.repo}/contents/{path}?ref={ref}", "-H", "Accept: application/vnd.github.raw")

    def create_tag(self, tag, sha):
        api(f"repos/{self.repo}/git/refs", "-f", f"ref=refs/tags/{tag}", "-f", f"sha={sha}")

    def head(self, branch):
        return api(f"repos/{self.repo}/branches/{branch}")["commit"]["sha"]

    def commit_to_develop(self, path, message):
        """Add a file on develop: unreleased work a hotfix must leave out."""
        api(f"repos/{self.repo}/contents/{path}", "-X", "PUT", "-f", f"message={message}",
            "-f", f"content={base64.b64encode(path.encode()).decode()}", "-f", "branch=develop")

    def merge_master_into_develop(self):
        # Stands in for the merge-back a cancelled release never reaches, so the next cycle's
        # release PR doesn't conflict on CHANGELOG.md.
        api(f"repos/{self.repo}/merges", "-f", "base=develop", "-f", "head=master",
            "-f", "commit_message=e2e: merge master into develop", check=False)


def unique_minor():
    return int(time.time() // 60) % 100000 + 1000


def scenario_version_mismatch(fx):
    """A tag whose version files disagree fails in prepare, before approval, and is withdrawn."""
    tag = f"v9.{unique_minor()}.0"
    fx.create_tag(tag, fx.head("master"))
    run = fx.finish(fx.dispatch("release.yml", tag, **{"dry-run": "true"}))
    jobs = fx.jobs(run["id"])
    expect(jobs["prepare"]["conclusion"] == "failure", f"{tag}: prepare fails")
    expect(jobs["publish"]["conclusion"] == "skipped", f"{tag}: publish never asks for approval")
    expect(fx.tag_sha(tag) is None, f"{tag}: tag withdrawn")
    log = fx.log(run["id"])
    expect("expected " + tag[1:] in log, f"{tag}: log names the mismatched file")
    expect("release failed" in log, f"{tag}: Slack payload reports the failure")


def scenario_stable_cycle(fx):
    """prepare-release → PR → merge → tag → release reaches approval; cancelling withdraws the tag."""
    version = f"0.{unique_minor()}.0"
    tag = f"v{version}"
    fx.merge_master_into_develop()
    prep = fx.finish(fx.dispatch("prepare-release.yml", "master", version=version, **{"dry-run": "false"}))
    expect(prep["conclusion"] == "success", f"{version}: prepare-release succeeds")
    branch = f"release/{version}"
    expect(f'"version": "{version}"' in fx.file("package.json", branch), f"{branch}: package.json has {version}")
    expect(f"## [{version}]" in fx.file("CHANGELOG.md", branch), f"{branch}: CHANGELOG has a {version} section")
    pr = json.loads(gh("pr", "list", "-R", fx.repo, "--head", branch, "--base", "master", "--json", "number"))
    expect(len(pr) == 1, f"{branch}: one release PR to master")

    since = time.time() - 5
    gh("pr", "merge", str(pr[0]["number"]), "-R", fx.repo, "--merge")
    tagger = fx.finish(fx.next_run("tag-on-merge.yml", branch, since))
    expect(tagger["conclusion"] == "success", f"{branch}: tag-on-merge succeeds")
    expect(fx.tag_sha(tag) == fx.head("master"), f"{tag}: on the merge commit")

    release = fx.next_run("release.yml", tag, since)
    jobs = fx.approval_then_cancel(release)
    expect(jobs["prepare"]["conclusion"] == "success" and jobs["build"]["conclusion"] == "success",
           f"{tag}: prepare and build pass before approval")
    wait(f"{tag} withdrawn", lambda: fx.tag_sha(tag) is None, timeout=300)
    expect(True, f"{tag}: cancelling withdraws the tag")
    fx.merge_master_into_develop()


def scenario_rc_cycle(fx):
    """prepare-release X.Y.Z-rc.1 commits on the release branch, tags, and dispatches a prerelease."""
    version = f"0.{unique_minor()}.0"
    rc = f"{version}-rc.1"
    tag = f"v{rc}"
    prep = fx.finish(fx.dispatch("prepare-release.yml", "master", version=rc, **{"dry-run": "false"}))
    expect(prep["conclusion"] == "success", f"{rc}: prepare-release succeeds")
    branch = f"release/{version}"
    expect(f'"version": "{rc}"' in fx.file("package.json", branch), f"{branch}: package.json has {rc}")
    expect(fx.tag_sha(tag) == fx.head(branch), f"{tag}: on the release branch head")
    prs = json.loads(gh("pr", "list", "-R", fx.repo, "--head", branch, "--json", "number"))
    expect(prs == [], f"{branch}: no PR for an RC")
    rc_commit = api(f"repos/{fx.repo}/commits/{branch}")
    expect([f["filename"] for f in rc_commit["files"]] == ["package.json"], f"{branch}: the RC commit leaves CHANGELOG.md alone")

    release = fx.next_run("release.yml", tag, created_at(prep))
    fx.approval_then_cancel(release)
    log = fx.log(release)
    expect("prerelease=true" in log and "dist-tag=rc" in log, f"{tag}: classified as a prerelease under rc")
    wait(f"{tag} withdrawn", lambda: fx.tag_sha(tag) is None, timeout=300)
    expect(True, f"{tag}: cancelling withdraws the tag")


def scenario_hotfix_cycle(fx):
    """base: hotfix cuts hotfix/X.Y.Z+1 from the latest stable tag, without develop's unreleased work."""
    stable = sorted(
        (tuple(int(p) for p in t[1:].split(".")), t)
        for t in fx.tags()
        if t.startswith("v") and t[1:].replace(".", "").isdigit() and t.count(".") == 2
    )
    if not stable:
        raise Failed("the fixture has no stable tag to hotfix")
    (major, minor, patch), base_tag = stable[-1]
    marker = f"e2e/unreleased-{unique_minor()}.txt"
    fx.commit_to_develop(marker, "feat: unreleased work on develop (e2e)")
    rc = f"{major}.{minor}.{patch + 1}-rc.{unique_minor()}"
    tag = f"v{rc}"
    prep = fx.finish(fx.dispatch("prepare-release.yml", "master", version=rc, base="hotfix", **{"dry-run": "false"}))
    expect(prep["conclusion"] == "success", f"{rc}: prepare-release with base hotfix succeeds")
    branch = f"hotfix/{major}.{minor}.{patch + 1}"
    compare = api(f"repos/{fx.repo}/compare/{base_tag}...{branch}")
    expect(compare["behind_by"] == 0, f"{branch}: contains {base_tag}")
    files = [f["filename"] for f in api(f"repos/{fx.repo}/compare/{base_tag}...{branch}")["files"]]
    expect(marker not in files, f"{branch}: leaves out develop's unreleased {marker}")

    release = fx.next_run("release.yml", tag, created_at(prep))
    fx.approval_then_cancel(release)
    wait(f"{tag} withdrawn", lambda: fx.tag_sha(tag) is None, timeout=300)
    expect(True, f"{tag}: cancelling withdraws the tag")


def created_at(run):
    return calendar.timegm(time.strptime(run["created_at"], "%Y-%m-%dT%H:%M:%SZ"))


SCENARIOS = {
    "version-mismatch": scenario_version_mismatch,
    "stable-cycle": scenario_stable_cycle,
    "rc-cycle": scenario_rc_cycle,
    "hotfix-cycle": scenario_hotfix_cycle,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default=FIXTURE)
    parser.add_argument("--only", nargs="*", choices=sorted(SCENARIOS))
    args = parser.parse_args()
    fx = Fixture(args.fixture)
    failed = []
    for name in args.only or SCENARIOS:
        print(f"▶ {name}")
        try:
            SCENARIOS[name](fx)
        except Exception as e:  # one broken scenario must not hide the others
            print(f"  ✗ {type(e).__name__ if not isinstance(e, Failed) else 'failed'}: {e}")
            failed.append(name)
    print(f"\n{len(failed)} of {len(args.only or SCENARIOS)} scenarios failed" + (f": {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
