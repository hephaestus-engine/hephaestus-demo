"""Reading a duration a person wrote."""

import re

# Hours, minutes and seconds, each optional but in that order, after an
# optional sign: `2h`, `45m`, `1h30m`, `90s`, `1h5m30s`, `-15m`.
_UNIT_FORM = re.compile(r"(?P<sign>-)?(?:(?P<h>\d+)h)?(?:(?P<m>\d+)m)?(?:(?P<s>\d+)s)?")


def parse_duration(text: str) -> int:
    """The number of seconds in a duration written in the unit form.

    The unit form is hours, minutes and seconds, each optional but in that
    order: `2h`, `45m`, `1h30m`, `90s`, `1h5m30s`. Case and surrounding
    spaces do not matter. A leading `-` makes the duration negative: the log
    records a correction as a negative entry, such as `-15m`.

    Raises ValueError, naming the input, for anything else.
    """
    cleaned = text.strip().lower()
    match = _UNIT_FORM.fullmatch(cleaned)
    if match is None or not any(match.group(unit) for unit in ("h", "m", "s")):
        raise ValueError(f"not a duration: {text!r}")
    seconds = int(match["h"] or 0) * 3600 + int(match["m"] or 0) * 60 + int(match["s"] or 0)
    return -seconds if match["sign"] else seconds
