"""Reading a duration a person wrote."""

import re

# Hours, minutes and seconds, each optional but in that order, after an
# optional sign: `2h`, `45m`, `1h30m`, `90s`, `1h5m30s`, `-15m`.
_UNIT_FORM = re.compile(r"(?P<sign>-)?(?:(?P<h>\d+)h)?(?:(?P<m>\d+)m)?(?:(?P<s>\d+)s)?")
_CLOCK_FORM = re.compile(r"(?P<sign>-)?(?P<h>\d+):(?P<m>[0-5]\d)")


def parse_duration(text: str) -> int:
    """Return the number of seconds in a unit or clock form duration.

    The unit form is hours, minutes and seconds, each optional but in that
    order: `2h`, `45m`, `1h30m`, `90s`, `1h5m30s`. The clock form is `H:MM`,
    with at least one digit of hours and exactly two digits of minutes from
    `00` to `59`. A leading `-` makes either form negative. Case and
    surrounding spaces do not matter.

    Raise ValueError, naming the input, for anything else.
    """
    cleaned = text.strip().lower()
    clock = _CLOCK_FORM.fullmatch(cleaned)
    if clock is not None:
        seconds = int(clock["h"]) * 3600 + int(clock["m"]) * 60
        return -seconds if clock["sign"] else seconds
    match = _UNIT_FORM.fullmatch(cleaned)
    if match is None or not any(match.group(unit) for unit in ("h", "m", "s")):
        raise ValueError(f"not a duration: {text!r}")
    seconds = int(match["h"] or 0) * 3600 + int(match["m"] or 0) * 60 + int(match["s"] or 0)
    return -seconds if match["sign"] else seconds
