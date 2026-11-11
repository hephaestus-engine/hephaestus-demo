import pytest

from durasum.parse import parse_duration


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("2h", 7200),
        ("45m", 2700),
        ("90s", 90),
        ("1h30m", 5400),
        ("1h5m30s", 3930),
        ("0m", 0),
        (" 1H30M ", 5400),
    ],
)
def test_the_unit_form_is_read(text, seconds):
    assert parse_duration(text) == seconds


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("-15m", -900),
        ("-1h30m", -5400),
        ("-90s", -90),
    ],
)
def test_a_leading_minus_is_a_correction(text, seconds):
    assert parse_duration(text) == seconds


@pytest.mark.parametrize(
    "text",
    ["", " ", "-", "h", "1x", "15", "1m1h", "--15m", "+15m", "1.5h", "1h 30m", "1:30"],
)
def test_anything_else_is_refused_and_named(text):
    with pytest.raises(ValueError) as refused:
        parse_duration(text)
    assert repr(text) in str(refused.value)
