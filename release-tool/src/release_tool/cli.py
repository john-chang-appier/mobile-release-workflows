import argparse
import sys
from pathlib import Path

from . import config, locators, versions


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

    args = parser.parse_args(argv)
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
