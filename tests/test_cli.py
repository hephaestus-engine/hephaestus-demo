from durasum.cli import main


def test_total_prints_the_logs_total(tmp_path, capsys):
    log = tmp_path / "work.log"
    log.write_text("30m  review\n20m  stand-up\n-5m  correction\n", encoding="utf-8")

    assert main(["total", str(log)]) == 0

    assert capsys.readouterr().out == "45m\n"


def test_total_in_seconds(tmp_path, capsys):
    log = tmp_path / "work.log"
    log.write_text("1h30m  planning\n45m  review\n", encoding="utf-8")

    assert main(["total", str(log), "--seconds"]) == 0

    assert capsys.readouterr().out == "8100\n"


def test_add_then_total(tmp_path, capsys):
    log = tmp_path / "work.log"

    assert main(["add", str(log), "25m", "write", "the", "notes"]) == 0
    assert main(["total", str(log)]) == 0

    assert log.read_text(encoding="utf-8") == "25m  write the notes\n"
    assert capsys.readouterr().out == "25m\n"


def test_add_takes_a_correction_as_written(tmp_path, capsys):
    log = tmp_path / "work.log"
    log.write_text("1h  planning\n", encoding="utf-8")

    assert main(["add", str(log), "-15m", "correction:", "planning", "ran", "short"]) == 0
    assert main(["add", str(log), "--", "-5m", "correction"]) == 0
    assert main(["total", str(log), "--seconds"]) == 0

    assert log.read_text(encoding="utf-8").splitlines()[1:] == [
        "-15m  correction: planning ran short",
        "-5m  correction",
    ]
    assert capsys.readouterr().out == "2400\n"


def test_add_without_a_description_exits_2(tmp_path, capsys):
    log = tmp_path / "work.log"

    assert main(["add", str(log), "20m"]) == 2

    assert not log.exists()
    assert "a duration and a description" in capsys.readouterr().err


def test_an_unreadable_log_exits_2_and_says_where(tmp_path, capsys):
    log = tmp_path / "work.log"
    log.write_text("30m  review\nsoon  later\n", encoding="utf-8")

    assert main(["total", str(log)]) == 2

    assert "line 2: not a duration: 'soon'" in capsys.readouterr().err


def test_a_missing_log_exits_2(tmp_path, capsys):
    assert main(["total", str(tmp_path / "absent.log")]) == 2

    assert "durasum:" in capsys.readouterr().err


def test_add_refuses_a_duration_it_could_not_read_back(tmp_path, capsys):
    log = tmp_path / "work.log"

    assert main(["add", str(log), "soon", "later"]) == 2

    assert not log.exists()
    assert "not a duration: 'soon'" in capsys.readouterr().err
