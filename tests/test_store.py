import stat
import sys

import pytest

from durasum.store import append_entry


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

    assert [p.name for p in tmp_path.iterdir()] == ["work.log"]


def test_a_failed_write_leaves_the_old_log_whole(tmp_path, monkeypatch):
    log = tmp_path / "work.log"
    log.write_bytes(b"45m  review\n")

    def disk_full(*args):
        raise OSError("no space left on device")

    monkeypatch.setattr("durasum.store.os.replace", disk_full)

    with pytest.raises(OSError):
        append_entry(log, "20m", "stand-up")

    assert log.read_bytes() == b"45m  review\n"
    assert [p.name for p in tmp_path.iterdir()] == ["work.log"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_the_log_keeps_its_permissions(tmp_path):
    log = tmp_path / "work.log"
    log.write_bytes(b"45m  review\n")
    log.chmod(0o640)

    append_entry(log, "20m", "stand-up")

    assert stat.S_IMODE(log.stat().st_mode) == 0o640
