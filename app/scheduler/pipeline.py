import asyncio
import logging
from datetime import datetime, date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import AppConfig, CategoryConfig
from app.fetchers.base import RawItem
from app.fetchers.registry import get_fetcher
from app.ai.processor import process_items
from app.models.item import Item
from app.models.run_log import RunLog
from app.push.feishu import push_key_items
from app.scheduler.dedup import filter_new_items

logger = logging.getLogger(__name__)


async def _fetch_category(category: CategoryConfig) -> list[RawItem]:
    enabled = [s for s in category.sources if s.enabled]
    results = await asyncio.gather(
        *[get_fetcher(s).fetch() for s in enabled],
        return_exceptions=True,
    )
    items: list[RawItem] = []
    for src, result in zip(enabled, results):
        if isinstance(result, Exception):
            logger.error("Source %r fetch error: %s", src.name, result)
        else:
            items.extend(result)
    return items


_DAILY_LIMIT = 50


def _today_count(category_slug: str, db: Session) -> int:
    today = date.today()
    return (
        db.query(func.count(Item.id))
        .filter(
            Item.category_slug == category_slug,
            func.date(Item.fetched_at) == today,
        )
        .scalar()
        or 0
    )


def _save_items(
    raw_items: list[RawItem],
    ai_results: list,
    category: CategoryConfig,
    db: Session,
) -> list[Item]:
    saved: list[Item] = []
    today_count = _today_count(category.slug, db)
    for raw, ai in zip(raw_items, ai_results):
        if today_count >= _DAILY_LIMIT:
            logger.info("Daily limit %d reached for %s, skipping rest", _DAILY_LIMIT, category.slug)
            break
        item_score = getattr(ai, "score", 0.0) or 0.0
        if item_score < category.min_save_score:
            logger.debug("Score %.1f below min_save_score %.1f, skipping %r",
                         item_score, category.min_save_score, raw.title)
            continue
        ai_extra = None
        if hasattr(ai, "ai_extra") and ai.ai_extra:
            ai_extra = ai.ai_extra.model_dump()
        if hasattr(ai, "work_impact") and ai.work_impact:
            ai_extra = ai_extra or {}
            ai_extra["work_impact"] = ai.work_impact
        if hasattr(ai, "title_zh") and ai.title_zh:
            ai_extra = ai_extra or {}
            ai_extra["title_zh"] = ai.title_zh

        item = Item(
            source_id=0,
            category_slug=category.slug,
            title=raw.title,
            url=raw.url,
            raw_text=(raw.raw_text[:2000] if raw.raw_text else None),
            summary_zh=getattr(ai, "summary_zh", None),
            score=getattr(ai, "score", None),
            is_key=getattr(ai, "is_key", False),
            content_tag=getattr(ai, "content_tag", None),
            ai_extra=ai_extra,
            published_at=raw.published_at,
            dedup_hash=raw.extra["dedup_hash"],
        )
        db.add(item)
        try:
            db.flush()
            saved.append(item)
            today_count += 1
        except Exception as exc:
            db.rollback()
            logger.warning("Skip duplicate item %r: %s", raw.url, exc)
    db.commit()
    return saved


def run_pipeline(
    slot: str,
    categories: list[CategoryConfig],
    db: Session,
    config: AppConfig,
    dry_run: bool = False,
) -> dict:
    summary: dict = {"total_fetched": 0, "total_new": 0, "categories": {}}
    all_key_items: list[Item] = []

    for category in categories:
        if slot not in category.schedule or not category.enabled:
            continue

        run_log = RunLog(slot=slot, category_slug=category.slug,
                         started_at=datetime.utcnow(), status="running",
                         items_fetched=0, items_new=0)
        db.add(run_log)
        db.commit()

        try:
            raw_items = asyncio.run(_fetch_category(category))
            new_items = filter_new_items(raw_items, db, config.settings.dedup_days)
            ai_results = process_items(new_items, category, dry_run=dry_run)
            saved = _save_items(new_items, ai_results, category, db)

            key_items = [i for i in saved if i.is_key]
            all_key_items.extend(key_items)

            run_log.status = "success"
            run_log.items_fetched = len(raw_items)
            run_log.items_new = len(saved)
            run_log.finished_at = datetime.utcnow()
            db.commit()

            summary["categories"][category.slug] = {
                "fetched": len(raw_items), "new": len(saved), "key": len(key_items)
            }
            summary["total_fetched"] += len(raw_items)
            summary["total_new"] += len(saved)

        except Exception as exc:
            logger.error("Pipeline error for %s: %s", category.slug, exc)
            run_log.status = "failed"
            run_log.error_msg = str(exc)
            run_log.finished_at = datetime.utcnow()
            db.commit()
            summary["categories"][category.slug] = {"error": str(exc)}

    push_key_items(slot, all_key_items, db, dry_run=dry_run)
    return summary
