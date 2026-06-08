import hashlib
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.fetchers.base import RawItem
from app.models.item import Item


def compute_hash(url: str) -> str:
    """
    Compute a SHA256 hash of the normalized URL.

    Normalizes the URL by stripping whitespace and converting to lowercase
    to ensure consistent hashing regardless of minor URL variations.

    Args:
        url: The URL to hash

    Returns:
        A 64-character hexadecimal SHA256 hash
    """
    normalized = url.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


def filter_new_items(
    raw_items: list[RawItem],
    db: Session,
    dedup_days: int = 7,
) -> list[RawItem]:
    """
    Filter out duplicate items based on a 7-day sliding window.

    Removes items that:
    1. Already exist in the database within the dedup window
    2. Have duplicate URLs within the current batch

    Adds a dedup_hash to the extra field of new items.

    Args:
        raw_items: List of raw items from fetchers
        db: SQLAlchemy database session
        dedup_days: Number of days to look back for duplicates (default: 7)

    Returns:
        List of RawItem objects that are new (not duplicates)
    """
    cutoff = datetime.utcnow() - timedelta(days=dedup_days)
    existing: set[str] = {
        row[0]
        for row in db.query(Item.dedup_hash).filter(Item.fetched_at >= cutoff).all()
    }

    new_items: list[RawItem] = []
    seen: set[str] = set()
    for item in raw_items:
        h = compute_hash(item.url)
        if h not in existing and h not in seen:
            item.extra["dedup_hash"] = h
            new_items.append(item)
            seen.add(h)
    return new_items
