import hashlib
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.fetchers.base import RawItem
from app.models.item import Item


def compute_hash(url: str) -> str:
    normalized = url.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


def filter_new_items(
    raw_items: list[RawItem],
    db: Session,
    dedup_days: int = 7,
) -> list[RawItem]:
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
