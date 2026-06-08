from __future__ import annotations

from app.ai.banking import process_banking_batch
from app.ai.tech import process_tech_batch
from app.ai.startup import process_startup_batch
from app.config import CategoryConfig
from app.fetchers.base import RawItem

_DEPTH_MAP = {
    "light": process_tech_batch,
    "medium": process_tech_batch,
    "medium_deep": process_banking_batch,
    "deep": process_startup_batch,
}


def process_items(
    items: list[RawItem],
    category: CategoryConfig,
    dry_run: bool = False,
) -> list:
    processor = _DEPTH_MAP.get(category.depth_level)
    if processor is None:
        raise ValueError(f"Unknown depth_level: {category.depth_level!r}")
    return processor(items, category, dry_run=dry_run)
