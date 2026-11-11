"""Total the durations in a plain-text work log."""

from durasum.fmt import format_duration
from durasum.log import Entry, LogError, read_entries, total
from durasum.parse import parse_duration

__all__ = [
    "Entry",
    "LogError",
    "format_duration",
    "parse_duration",
    "read_entries",
    "total",
]
