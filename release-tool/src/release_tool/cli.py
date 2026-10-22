import argparse
import sys
from pathlib import Path

from . import ci, config, locators, versions


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="release-tool")
    groups = parser.add_subparsers(dest="group", required=True)

    cfg = groups.add_parser("config").add_subparsers(dest="command", required=True)
    validate = cfg.add_parser("validate")
    validate.add_argument("--repo", type=Path, default=Path("."))

    get = cfg.add_parser("get")
    get.add_argument("key", choices=["platform", "working-directory", "tag-prefix"])
    get.add_argument("--repo", type=Path, default=Path("."))

    version = groups.add_parser("version").add_subparsers(dest="command", required=True)
    verify = version.add_parser("verify")
    verify.add_argument("tag")
    verify.add_argument("--repo", type=Path, default=Path("."))

    write = version.add_parser("write")
    write.add_argument("version")
    write.add_argument("--repo", type=Path, default=Path("."))

    ci_cmd = groups.add_parser("ci").add_subparsers(dest="command", required=True)
    ci_verify = ci_cmd.add_parser("verify")
    ci_verify.add_argument("--runs", type=Path, required=True, help="GET /repos/{repo}/actions/runs?head_sha=…")
    ci_verify.add_argument("--statuses", type=Path, required=True, help="GET /repos/{repo}/commits/{sha}/status")
    ci_verify.add_argument("--exclude-path", required=True, help="workflow file of the running release, ignored")

    args = parser.parse_args(argv)
    if args.group == "ci":
        return _ci_verify(args)
    try:
        data = config.load(args.repo)
        if args.group == "config" and args.command == "get":
            print(data[args.key])
        if args.group == "version" and args.command == "verify":
            return _verify(args, data)
        if args.group == "version" and args.command == "write":
            for f in versions.write(args.repo, data, args.version):
                print(f)
    except (config.ConfigError, locators.LocatorError, versions.VersionError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


def _verify(args, data) -> int:
    expected = versions.version_from_tag(data, args.tag)
    bad = versions.mismatches(args.repo, data, expected)
    for line in bad:
        print(f"error: {line}", file=sys.stderr)
    return 1 if bad else 0


CI_PENDING = 2


def _ci_verify(args) -> int:
    """Exit 0 when CI passed, 1 when it failed, 2 while it is still running or not started."""
    v = ci.verdict(args.runs, args.statuses, args.exclude_path)
    for line in v.failed:
        print(f"error: {line}", file=sys.stderr)
    for line in v.pending:
        print(f"pending: {line}", file=sys.stderr)
    if v.failed:
        return 1
    return CI_PENDING if v.pending else 0
