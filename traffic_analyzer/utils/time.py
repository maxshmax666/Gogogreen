from __future__ import annotations

from datetime import datetime, timezone


def parse_ts_to_epoch_ms(value: int | float | str) -> int:
    if isinstance(value, (int, float)):
        n = int(value)
        if n < 10_000_000_000:
            return n * 1000
        return n
    text = str(value).strip()
    if text.isdigit():
        return parse_ts_to_epoch_ms(int(text))
    dt = datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    return int(dt.timestamp() * 1000)


def day_part(epoch_ms: int) -> str:
    hour = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).hour
    if 6 <= hour < 11:
        return "morning"
    if 11 <= hour < 17:
        return "day"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def slot_key(epoch_ms: int, slot_minutes: int) -> str:
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    minute = (dt.minute // slot_minutes) * slot_minutes
    return f"{dt.hour:02d}:{minute:02d}"
