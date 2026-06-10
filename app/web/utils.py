"""Shared utilities for web routes."""
from datetime import datetime, timedelta

_CST_UTC_OFFSET = timedelta(hours=8)


def since_utc(days: int) -> datetime:
    """Return naive UTC datetime for start-of-day (CST) N days ago.

    fetched_at is stored as UTC (SQLite CURRENT_TIMESTAMP). Users are in
    CST (UTC+8), so 'today' for them starts at UTC 16:00 the previous day.
    This function converts CST midnight → UTC so filter comparisons are correct.
    """
    now_cst = datetime.utcnow() + _CST_UTC_OFFSET
    target_cst_date = now_cst.date() - timedelta(days=days - 1)
    target_cst_midnight = datetime.combine(target_cst_date, datetime.min.time())
    return target_cst_midnight - _CST_UTC_OFFSET


def cst_date_n_days_ago(days: int):
    """Return CST date N days ago, for display purposes only."""
    now_cst = datetime.utcnow() + _CST_UTC_OFFSET
    return (now_cst.date() - timedelta(days=days - 1))


def cst_today():
    """Return today's date in CST."""
    return (datetime.utcnow() + _CST_UTC_OFFSET).date()
