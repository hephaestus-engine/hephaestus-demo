import pytest

from durasum.fmt import format_duration


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (0, "0s"),
        (59, "59s"),
        (60, "1m"),
        (90, "1m 30s"),
        (2700, "45m"),
        (3599, "59m 59s"),
    ],
)
def test_under_an_hour(seconds, text):
    assert format_duration(seconds) == text


@pytest.mark.parametrize(("seconds", "text"), [(-900, "-15m"), (-90, "-1m 30s")])
def test_a_negative_duration_carries_one_sign(seconds, text):
    assert format_duration(seconds) == text


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (3600, "1h"),
        (5400, "1h 30m"),
        (3661, "1h 1m 1s"),
        (-5400, "-1h 30m"),
    ],
)
def test_hours_and_minutes(seconds, text):
    assert format_duration(seconds) == text
