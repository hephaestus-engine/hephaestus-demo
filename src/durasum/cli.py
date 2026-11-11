"""The `durasum` command.

    durasum total LOG [--seconds]          print the log's total
    durasum add LOG DURATION DESCRIPTION   add an entry to the end of the log

Unreadable input exits with status 2 and says why on standard error.
"""

import argparse
import sys
from collections.abc import Sequence

from durasum.fmt import format_duration
from durasum.log import read_entries, total
from durasum.store import append_entry


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="durasum", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    total_cmd = commands.add_parser("total", help="print the total of a log")
    total_cmd.add_argument("log", help="the log file")
    total_cmd.add_argument("--seconds", action="store_true", help="print a number of seconds")

    add_cmd = commands.add_parser("add", help="add an entry to the end of a log")
    add_cmd.add_argument("log", help="the log file; created if missing")
    add_cmd.add_argument("duration", help="for example 1h30m, 45m or -15m")
    add_cmd.add_argument("description", nargs="+", help="what the time was spent on")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "total":
            with open(args.log, encoding="utf-8") as log:
                seconds = total(read_entries(log))
            print(seconds if args.seconds else format_duration(seconds))
        else:
            append_entry(args.log, args.duration, " ".join(args.description))
    except (OSError, ValueError) as exc:
        print(f"durasum: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
