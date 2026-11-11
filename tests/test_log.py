import pytest

from durasum.log import Entry, LogError, read_entries, total


def test_each_line_is_a_duration_and_a_description():
    lines = ["45m  review the parser change\n", "30m\twrite the notes\n"]

    assert read_entries(lines) == [
        Entry(seconds=2700, description="review the parser change", line=1),
        Entry(seconds=1800, description="write the notes", line=2),
    ]


def test_comments_and_blank_lines_are_skipped_but_counted():
    lines = ["# monday\n", "\n", "20m  stand-up\n"]

    assert read_entries(lines) == [Entry(seconds=1200, description="stand-up", line=3)]


def test_a_line_may_have_no_description():
    assert read_entries(["15m\n"]) == [Entry(seconds=900, description="", line=1)]


def test_an_unreadable_line_is_named_by_its_number():
    with pytest.raises(LogError, match=r"line 2: not a duration: 'soon'"):
        read_entries(["10m  first\n", "soon  second\n"])


def test_the_total_subtracts_corrections():
    entries = read_entries(["45m  review\n", "-15m  correction: it ran short\n"])

    assert total(entries) == 1800


def test_an_empty_log_totals_zero():
    assert total(read_entries([])) == 0
