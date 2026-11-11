import multiprocessing
import os
import stat
import sys

import pytest

from durasum.store import append_entry


def _beside(directory):
    """The names in a log's directory, sorted."""
    return sorted(p.name for p in directory.iterdir())


def test_an_entry_is_added_to_the_end(tmp_path):
    log = tmp_path / "work.log"
    log.write_bytes(b"45m  review\n")

    append_entry(log, "20m", "stand-up")

    assert log.read_bytes() == b"45m  review\n20m  stand-up\n"


def test_a_missing_log_is_created(tmp_path):
    log = tmp_path / "work.log"

    append_entry(log, "1h", "planning")

    assert log.read_bytes() == b"1h  planning\n"


def test_existing_lines_are_kept_byte_for_byte(tmp_path):
    log = tmp_path / "work.log"
    before = "# monday\r\n45m  café chat\r\n".encode()
    log.write_bytes(before)

    append_entry(log, "-15m", "correction")

    assert log.read_bytes() == before + b"-15m  correction\r\n"


def test_a_last_line_without_a_newline_is_ended_first(tmp_path):
    log = tmp_path / "work.log"
    log.write_bytes(b"45m  review")

    append_entry(log, "20m", "stand-up")

    assert log.read_bytes() == b"45m  review\n20m  stand-up\n"


@pytest.mark.parametrize(
    ("duration", "description"),
    [("soon", "later"), ("20m", "two\nlines")],
)
def test_a_refused_entry_leaves_the_log_untouched(tmp_path, duration, description):
    log = tmp_path / "work.log"
    log.write_bytes(b"45m  review\n")

    with pytest.raises(ValueError):
        append_entry(log, duration, description)

    assert log.read_bytes() == b"45m  review\n"
    assert [p.name for p in tmp_path.iterdir()] == ["work.log"]


def test_no_temporary_file_is_left_behind(tmp_path):
    log = tmp_path / "work.log"

    append_entry(log, "20m", "stand-up")
    append_entry(log, "10m", "notes")

    assert _beside(tmp_path) == [".work.log.lock", "work.log"]


def test_a_failed_write_leaves_the_old_log_whole(tmp_path, monkeypatch):
    log = tmp_path / "work.log"
    log.write_bytes(b"45m  review\n")

    def disk_full(*args):
        raise OSError("no space left on device")

    monkeypatch.setattr("durasum.store.os.replace", disk_full)

    with pytest.raises(OSError):
        append_entry(log, "20m", "stand-up")

    assert log.read_bytes() == b"45m  review\n"
    assert _beside(tmp_path) == [".work.log.lock", "work.log"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_the_log_keeps_its_permissions(tmp_path):
    log = tmp_path / "work.log"
    log.write_bytes(b"45m  review\n")
    log.chmod(0o640)

    append_entry(log, "20m", "stand-up")

    assert stat.S_IMODE(log.stat().st_mode) == 0o640


def test_adds_at_the_same_time_keep_every_entry(tmp_path):
    log = tmp_path / "work.log"
    entries = [(log, "1m", f"entry {n}") for n in range(40)]

    with multiprocessing.get_context("spawn").Pool(8) as pool:
        pool.starmap(append_entry, entries)

    lines = log.read_text(encoding="utf-8").splitlines()
    assert sorted(lines) == sorted(f"1m  entry {n}" for n in range(40))


def test_a_log_reached_through_a_link_is_written_where_it_points(tmp_path):
    real = tmp_path / "synced" / "work.log"
    real.parent.mkdir()
    real.write_bytes(b"45m  review\n")
    link = tmp_path / "work.log"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("this account may not create symbolic links")

    append_entry(link, "20m", "stand-up")

    assert link.is_symlink()
    assert real.read_bytes() == b"45m  review\n20m  stand-up\n"
    assert _beside(real.parent) == [".work.log.lock", "work.log"]


@pytest.mark.skipif(getattr(os, "geteuid", lambda: 1)() == 0, reason="root may write any file")
def test_a_read_only_log_is_refused_and_left_whole(tmp_path):
    log = tmp_path / "work.log"
    log.write_bytes(b"45m  review\n")
    log.chmod(stat.S_IREAD)

    with pytest.raises(PermissionError, match="read-only"):
        append_entry(log, "20m", "stand-up")

    log.chmod(stat.S_IREAD | stat.S_IWRITE)
    assert log.read_bytes() == b"45m  review\n"
    assert _beside(tmp_path) == [".work.log.lock", "work.log"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_a_new_log_gets_the_permissions_of_any_new_file(tmp_path):
    log = tmp_path / "work.log"
    previous = os.umask(0o027)
    try:
        append_entry(log, "20m", "stand-up")
    finally:
        os.umask(previous)

    assert stat.S_IMODE(log.stat().st_mode) == 0o640
