import argparse
import json
import sys
from pathlib import Path

from . import changelog, ci, config, locators, native, slack, versions

CI_PENDING = 2
ERRORS = (config.ConfigError, locators.LocatorError, versions.VersionError)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="release-tool")
    commands = parser.add_subparsers(dest="command", required=True)
    repo = argparse.ArgumentParser(add_help=False)
    repo.add_argument("--repo", type=Path, default=Path("."))

    cfg = commands.add_parser("config").add_subparsers(dest="subcommand", required=True)
    cfg.add_parser("validate", parents=[repo]).set_defaults(func=_config_validate)
    get = cfg.add_parser("get", parents=[repo])
    get.add_argument("key", choices=["platform", "working-directory", "tag-prefix", "channels"])
    get.set_defaults(func=_config_get)

    version = commands.add_parser("version").add_subparsers(dest="subcommand", required=True)
    verify = version.add_parser("verify", parents=[repo])
    verify.add_argument("tag")
    verify.set_defaults(func=_version_verify)
    write = version.add_parser("write", parents=[repo])
    write.add_argument("version")
    write.set_defaults(func=_version_write)

    ci_ = commands.add_parser("ci").add_subparsers(dest="subcommand", required=True)
    ci_verify = ci_.add_parser("verify")
    ci_verify.add_argument("--runs", type=Path, required=True, help="GET /repos/{repo}/actions/runs?head_sha=…")
    ci_verify.add_argument("--statuses", type=Path, required=True, help="GET /repos/{repo}/commits/{sha}/status")
    ci_verify.add_argument("--exclude-path", required=True, help="workflow file of the running release, ignored")
    ci_verify.set_defaults(func=_ci_verify)

    plan = commands.add_parser("plan", help="resume plan: publish, skip-publish, or fail")
    plan.add_argument("--tag-exists", choices=["true", "false"], required=True)
    plan.add_argument("--published", choices=["true", "false"], required=True)
    plan.set_defaults(func=_plan)

    classify = commands.add_parser("classify", parents=[repo], help="prerelease flag, npm dist-tag, tag name")
    classify.add_argument("version")
    classify.set_defaults(func=_classify)

    hotfix = commands.add_parser("hotfix-check", parents=[repo], help="print the stable tag a hotfix starts from")
    hotfix.add_argument("version")
    hotfix.add_argument("--tags", type=Path, required=True, help="file with one tag name per line")
    hotfix.set_defaults(func=_hotfix_check)

    log = commands.add_parser("changelog").add_subparsers(dest="subcommand", required=True)
    drop = log.add_parser("drop", help="remove one version's section")
    drop.add_argument("version")
    drop.add_argument("--file", type=Path, required=True)
    drop.set_defaults(func=lambda args: changelog.drop(args.file, args.version))

    drift = commands.add_parser("native-drift", parents=[repo], help="warn about outdated native pins; never fails")
    drift.add_argument("--list-repos", action="store_true", help="print the native repos to fetch tags for")
    drift.add_argument("--tags-dir", type=Path, help="one <owner>__<repo>.txt file of tag names per native repo")
    drift.set_defaults(func=_native_drift)

    msg = commands.add_parser("slack-message", help="Slack webhook payload for a release outcome")
    msg.add_argument("--outcome", choices=sorted(slack.HEADLINES), required=True)
    msg.add_argument("--repo-name", required=True)
    msg.add_argument("--version", required=True)
    msg.add_argument("--run-url", required=True)
    msg.add_argument("--artifact-url")
    msg.add_argument("--warnings", type=Path, help="file of warning lines, e.g. native-drift output")
    msg.add_argument("--merge-back-conflict", help="URL of a merge-back PR that has conflicts")
    msg.add_argument("--dry-run", action="store_true")
    msg.set_defaults(func=_slack_message)

    args = parser.parse_args(argv)
    try:
        return args.func(args) or 0
    except ERRORS as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def _config_validate(args):
    config.load(args.repo)


def _config_get(args):
    value = config.load(args.repo)[args.key]
    print("\n".join(value) if isinstance(value, list) else value)


def _version_verify(args) -> int:
    data = config.load(args.repo)
    expected = versions.version_from_tag(data, args.tag)
    mismatches = versions.mismatches(args.repo, data, expected)
    for line in mismatches:
        print(f"error: {line}", file=sys.stderr)
    return 1 if mismatches else 0


def _version_write(args):
    for f in versions.write(args.repo, config.load(args.repo), args.version):
        print(f)


def _ci_verify(args) -> int:
    """Exit 0 when CI passed, 1 when it failed, 2 while it is still running or not started."""
    verdict = ci.verdict(args.runs, args.statuses, args.exclude_path)
    for line in verdict.failed:
        print(f"error: {line}", file=sys.stderr)
    for line in verdict.pending:
        print(f"pending: {line}", file=sys.stderr)
    if verdict.failed:
        return 1
    return CI_PENDING if verdict.pending else 0


def _plan(args):
    if args.tag_exists == "false":
        print("fail")
    elif args.published == "true":
        print("skip-publish")
    else:
        print("publish")


def _classify(args):
    data = config.load(args.repo)
    versions.check(args.version)
    prerelease = versions.is_prerelease(args.version)
    print(f"prerelease={str(prerelease).lower()}")
    print(f"dist-tag={'rc' if prerelease else 'latest'}")
    print(f"tag={data['tag-prefix']}{args.version}")


def _hotfix_check(args):
    tags = args.tags.read_text().split()
    print(versions.check_hotfix(config.load(args.repo), args.version, tags))


def _native_drift(args):
    # Warnings only: drift must never block a release, so every failure becomes a line of output.
    try:
        data = config.load(args.repo)
        lines = native.repos(data) if args.list_repos else native.warnings(args.repo, data, args.tags_dir)
    except ERRORS as e:
        lines = [f"native-drift: {e}"]
    for line in lines:
        print(line)


def _slack_message(args):
    warnings = args.warnings.read_text().splitlines() if args.warnings and args.warnings.is_file() else []
    payload = slack.message(
        args.outcome,
        args.repo_name,
        args.version,
        args.run_url,
        artifact_url=args.artifact_url,
        warnings=[w for w in warnings if w.strip()],
        conflict_url=args.merge_back_conflict,
        dry_run=args.dry_run,
    )
    print(json.dumps(payload))
