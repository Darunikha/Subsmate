"""Date helpers used by subscription expiry and renewal logic."""
import calendar
from datetime import date

CYCLE_MONTHS = {"monthly": 1, "quarterly": 3, "yearly": 12}


def today():
    return date.today()


def add_months(value, months):
    """Add calendar months, clamping the day to the target month's length.

    Jan 31 + 1 month -> Feb 28 (or 29 in leap years).
    """
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def calculate_expiry(start_date, billing_cycle):
    """Expiry date for a billing period starting on ``start_date``."""
    try:
        months = CYCLE_MONTHS[billing_cycle]
    except KeyError as exc:
        raise ValueError(f"Unknown billing cycle: {billing_cycle}") from exc
    return add_months(start_date, months)


def month_key(value):
    return value.strftime("%Y-%m")


def month_range(start, end):
    """List of 'YYYY-MM' keys from start to end inclusive."""
    keys = []
    cursor = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    while cursor <= last:
        keys.append(month_key(cursor))
        cursor = add_months(cursor, 1)
    return keys
