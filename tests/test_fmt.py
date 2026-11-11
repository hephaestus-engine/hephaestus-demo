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


# The planted defect of demo 1 (demo/issues/01-hours-print-their-minutes-twice.md):
# the minutes are taken from the whole duration, not from what is left after the
# hours. Expected to fail until that demo's change lands, which removes this marker;
# with xfail_strict, a fix that leaves the marker fails the suite.
@pytest.mark.xfail(reason="demo 1: hours print their minutes twice")
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
