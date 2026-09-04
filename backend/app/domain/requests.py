"""Pure request-day expansion and validation."""

from datetime import date, timedelta


class RequestError(ValueError):
    pass


def request_days(
    *, start: date, end: date, partial_minutes: int | None, day_minutes: int = 480
) -> list[tuple[date, int]]:
    if end < start:
        raise RequestError("The end date cannot be before the start date.")
    if partial_minutes is not None and start != end:
        raise RequestError("Partial hours are only supported for a single-day request.")
    if partial_minutes is not None and not 0 < partial_minutes <= day_minutes:
        raise RequestError(f"A partial request must be between 1 and {day_minutes} minutes.")

    days = []
    cursor = start
    while cursor <= end:
        if cursor.isoweekday() <= 5:
            days.append((cursor, partial_minutes or day_minutes))
        cursor += timedelta(days=1)
    if not days:
        raise RequestError("The request contains no working days.")
    return days
