"""Reading a work log.

A log has one entry a line: a duration, then what the time was spent on. A
line starting with `#` is a comment, and blank lines are skipped:

    # monday
    1h30m  write the release notes
    45m    review the parser change
    -15m   correction: the review ran short
"""

from collections.abc import Iterable
from dataclasses import dataclass

from durasum.parse import parse_duration


class LogError(ValueError):
    """A log line that cannot be read, named by its line number."""


@dataclass(frozen=True)
class Entry:
    seconds: int
    description: str
    line: int


def read_entries(lines: Iterable[str]) -> list[Entry]:
    """The entries of a log, in order.

    Each line's first word is its duration, read by `parse_duration`; the rest
    of the line is the description. Raises LogError naming the first line
    that cannot be read.
    """
    entries = []
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        duration, *description = line.split(None, 1)
        try:
            seconds = parse_duration(duration)
        except ValueError as exc:
            raise LogError(f"line {number}: {exc}") from None
        entries.append(Entry(seconds=seconds, description="".join(description), line=number))
    return entries


def total(entries: Iterable[Entry]) -> int:
    """The sum of the entries' durations, in seconds; corrections subtract."""
    return sum(entry.seconds for entry in entries)
