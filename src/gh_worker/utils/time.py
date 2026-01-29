"""Time parsing utilities."""

import re
from datetime import timedelta


def parse_duration(duration_str: str) -> timedelta:
    """Parse duration string into timedelta.

    Args:
        duration_str: Duration string (e.g., '10m', '1h', '2d', '1h30m')

    Returns:
        timedelta object

    Raises:
        ValueError: If duration string format is invalid

    Examples:
        >>> parse_duration('10m')
        timedelta(seconds=600)
        >>> parse_duration('1h')
        timedelta(seconds=3600)
        >>> parse_duration('2d')
        timedelta(days=2)
        >>> parse_duration('1h30m')
        timedelta(seconds=5400)
    """
    if not duration_str:
        raise ValueError("Duration string cannot be empty")

    # Pattern to match time components (e.g., '1h', '30m', '2d')
    pattern = r"(\d+)([smhd])"
    matches = re.findall(pattern, duration_str.lower())

    if not matches:
        raise ValueError(
            f"Invalid duration format: {duration_str}. "
            "Expected format like '10m', '1h', '2d', or '1h30m'"
        )

    total_seconds = 0
    for value, unit in matches:
        value = int(value)
        if unit == "s":
            total_seconds += value
        elif unit == "m":
            total_seconds += value * 60
        elif unit == "h":
            total_seconds += value * 3600
        elif unit == "d":
            total_seconds += value * 86400

    return timedelta(seconds=total_seconds)
