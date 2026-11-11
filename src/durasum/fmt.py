"""Writing a duration for a person to read."""


def format_duration(seconds: int) -> str:
    """A number of seconds as `1h 30m`, `45m`, `1h 1m 1s` or `-15m`.

    Hours, minutes and seconds are shown only when they are not zero, so a
    whole hour is `1h`; zero is `0s`. A negative duration carries one leading
    `-`.
    """
    sign = "-" if seconds < 0 else ""
    remaining = abs(seconds)
    hours, rest = divmod(remaining, 3600)
    minutes, secs = divmod(remaining, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return sign + " ".join(parts)
