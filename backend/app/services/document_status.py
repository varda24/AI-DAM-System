from __future__ import annotations

from datetime import date, datetime, timezone


VALID = "VALID"
EXPIRING_SOON = "EXPIRING SOON"
EXPIRED = "EXPIRED"
UNKNOWN = "UNKNOWN"


def _to_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    return value


def calculate_document_status(
    expiry_date: date | datetime | None,
    today: date | None = None,
    warning_days: int = 30,
) -> str:
    """
    Calculate the current document status from its expiry date.

    Rules:
    - No expiry date -> UNKNOWN
    - Expiry date before today -> EXPIRED
    - Expiry date within warning_days -> EXPIRING SOON
    - Otherwise -> VALID
    """

    expiry = _to_date(expiry_date)

    if expiry is None:
        return UNKNOWN

    current_date = today or datetime.now(timezone.utc).date()

    if expiry < current_date:
        return EXPIRED

    days_remaining = (expiry - current_date).days

    if days_remaining <= warning_days:
        return EXPIRING_SOON

    return VALID


def days_until_expiry(
    expiry_date: date | datetime | None,
    today: date | None = None,
) -> int | None:
    expiry = _to_date(expiry_date)

    if expiry is None:
        return None

    current_date = today or datetime.now(timezone.utc).date()

    return (expiry - current_date).days