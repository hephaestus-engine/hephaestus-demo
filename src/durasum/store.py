"""Writing to a person's log file.

The log is the only copy of what a person recorded, and this module is the
only code that writes it. A write never truncates the file in place: the new
content goes to a temporary file beside it, is flushed to disk, and replaces
the log in one step, so a crash or a full disk leaves the old log whole.
Existing lines are kept byte for byte, line endings included.
"""

import os
import stat
import tempfile
from pathlib import Path

from durasum.parse import parse_duration


def append_entry(path: str | Path, duration: str, description: str) -> None:
    """Add one entry to the end of the log at `path`, creating it if needed.

    The duration is checked with `parse_duration` before anything is written,
    so an entry the log could not read back is refused with ValueError and
    the file is left untouched. The description must be one line.
    """
    parse_duration(duration)
    description = description.strip()
    if "\n" in description or "\r" in description:
        raise ValueError(f"a description is one line: {description!r}")

    path = Path(path)
    existing = path.read_bytes() if path.exists() else b""
    newline = b"\r\n" if b"\r\n" in existing else b"\n"
    if existing and not existing.endswith(b"\n"):
        existing += newline
    line = f"{duration.strip()}  {description}".rstrip().encode("utf-8") + newline
    _replace(path, existing + line)


def _replace(path: Path, content: bytes) -> None:
    """Write `content` to a temporary file beside `path`, then put it in place.

    The temporary file takes the log's permissions, so the replace does not
    change who may read the log.
    """
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        if path.exists():
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(handle, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
