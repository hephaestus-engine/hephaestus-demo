"""Writing to a person's log file.

The log is the only copy of what a person recorded, and this module is the
only code that writes it. A write never truncates the file in place: the new
content goes to a temporary file beside it, is flushed to disk, and replaces
the log in one step, so a crash or a full disk leaves the old log whole.
Existing lines are kept byte for byte, line endings included.

Two writers at once take turns. Each holds a lock on a file beside the log,
`.NAME.lock`, from reading the log to replacing it, so neither replaces the
log with a copy that lacks the other's entry. The lock file is empty and is
left in place: removing it would let a writer that is waiting on it lock a
file nobody else sees.
"""

import os
import stat
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from durasum.parse import parse_duration

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

# How long a writer waits for another to finish before it gives up.
LOCK_WAIT_S = 10.0
# How long a replace is retried on Windows while another program holds the log.
REPLACE_WAIT_S = 2.0


def append_entry(path: str | Path, duration: str, description: str) -> None:
    """Add one entry to the end of the log at `path`, creating it if needed.

    The duration is checked with `parse_duration` before anything is written,
    so an entry the log could not read back is refused with ValueError and
    the file is left untouched. The description must be one line. A log
    reached through a symbolic link is written where the link points, and the
    link is kept. A log the person may not write is refused with
    PermissionError, as an edit in place would be.
    """
    parse_duration(duration)
    description = description.strip()
    if "\n" in description or "\r" in description:
        raise ValueError(f"a description is one line: {description!r}")

    path = Path(os.path.realpath(path))
    with _locked(path):
        if path.exists() and not os.access(path, os.W_OK):
            raise PermissionError(f"the log is read-only: {path}")
        existing = path.read_bytes() if path.exists() else b""
        newline = b"\r\n" if b"\r\n" in existing else b"\n"
        if existing and not existing.endswith(b"\n"):
            existing += newline
        line = f"{duration.strip()}  {description}".rstrip().encode("utf-8") + newline
        _replace(path, existing + line)


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    """Hold the lock beside `path` while the block runs, waiting up to
    LOCK_WAIT_S for another writer to let it go; TimeoutError after that."""
    lock = os.open(path.with_name(f".{path.name}.lock"), os.O_RDWR | os.O_CREAT, 0o666)
    try:
        if sys.platform == "win32":
            deadline = time.monotonic() + LOCK_WAIT_S
            while True:
                try:
                    msvcrt.locking(lock, msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"another write to {path} did not finish") from None
                    time.sleep(0.01)
            try:
                yield
            finally:
                os.lseek(lock, 0, os.SEEK_SET)
                msvcrt.locking(lock, msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield
    finally:
        os.close(lock)


def _replace(path: Path, content: bytes) -> None:
    """Write `content` to a temporary file beside `path`, then put it in place.

    The new file takes the log's permissions, so the replace does not change
    who may read the log; a new log gets the permissions any new file would.
    """
    if path.exists():
        mode = stat.S_IMODE(path.stat().st_mode)
    else:
        mode = 0o666 & ~_umask()
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temporary, mode)
        _move(temporary, path)
    except BaseException:
        # The error that stopped the write is the one to report, not a
        # failure to clean up after it.
        with suppress(OSError):
            os.unlink(temporary)
        raise


def _move(source: str, target: Path) -> None:
    """`os.replace`, retried for up to REPLACE_WAIT_S on Windows.

    Windows refuses to replace a file another program has open, and a virus
    scanner, a search indexer or a sync client opens a file soon after it is
    written, for a moment. A read-only log never gets here (`append_entry`
    refuses it first), so a refusal here is that moment, and it passes.
    """
    deadline = time.monotonic() + REPLACE_WAIT_S
    while True:
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if sys.platform != "win32" or time.monotonic() > deadline:
                raise
            time.sleep(0.01)


def _umask() -> int:
    """The process's umask. Reading it means setting it, so it is set back at
    once; the command is single-threaded."""
    mask = os.umask(0)
    os.umask(mask)
    return mask
