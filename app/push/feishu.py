import logging
import os
from datetime import datetime, date, timedelta

import httpx
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.push_log import PushLog

logger = logging.getLogger(__name__)

_SLOT_LABELS = {"morning": "早间", "evening": "晚间"}
_CAT_LABELS = {"banking": "银行用户运营", "tech": "技术与 AI 工具", "startup": "个人创业"}
_FEATURED_LIMIT = 5


def _get_title(item: Item) -> str:
    if item.ai_extra and item.ai_extra.get("title_zh"):
        return item.ai_extra["title_zh"]
    return item.title


def _build_card(slot: str, featured: list[Item], key_items: list[Item]) -> dict:
    date_str = datetime.now().strftime("%Y-%m-%d")
    slot_label = _SLOT_LABELS.get(slot, slot)
    elements: list[dict] = []

    if featured:
        elements.append({"tag": "markdown", "content": "**🌟 今日精选**"})
        for i, item in enumerate(featured, 1):
            title = _get_title(item)
            summary = (item.summary_zh or "")[:80]
            cat = _CAT_LABELS.get(item.category_slug, item.category_slug)
            score_str = f"{item.score:.1f}" if item.score else "-"
            elements.append({
                "tag": "markdown",
                "content": f"{i}. [{title}]({item.url})\n   {summary}\n   _[{cat}] 评分 {score_str}_",
            })

    if key_items:
        elements.append({"tag": "markdown", "content": "---\n**📌 重点关注**"})
        for item in key_items:
            title = _get_title(item)
            summary = (item.summary_zh or item.title)[:80]
            elements.append({"tag": "markdown",
                              "content": f"• [{title}]({item.url})\n  {summary}"})

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text",
                          "content": f"每日精选 · {date_str} {slot_label}"},
                "template": "wathet",
            },
            "elements": elements,
        },
    }


def push_key_items(
    slot: str,
    key_items: list[Item],
    db: Session,
    webhook_url: str | None = None,
    dry_run: bool = False,
) -> bool:
    cutoff = date.today() - timedelta(days=1)
    featured = (
        db.query(Item)
        .filter(Item.fetched_at >= cutoff, Item.score.isnot(None))
        .order_by(desc(Item.score))
        .limit(_FEATURED_LIMIT)
        .all()
    )

    if not featured and not key_items:
        logger.info("Nothing to push for slot=%s", slot)
        return True

    pushed_ids: set[int] = set()
    for log in db.query(PushLog).filter_by(slot=slot).all():
        pushed_ids.update(log.item_ids)

    new_key = [i for i in key_items if i.id not in pushed_ids]

    if dry_run:
        logger.info("[dry-run] Would push %d featured + %d key items", len(featured), len(new_key))
        return True

    url = webhook_url or os.environ.get("FEISHU_WEBHOOK_URL")
    if not url:
        raise ValueError("FEISHU_WEBHOOK_URL not set")

    try:
        resp = httpx.post(url, json=_build_card(slot, featured, new_key), timeout=10)
        resp.raise_for_status()
        if resp.json().get("code") != 0:
            logger.error("Feishu error: %s", resp.json())
            return False
    except Exception as exc:
        logger.error("Feishu push failed: %s", exc)
        return False

    all_ids = [i.id for i in featured] + [i.id for i in new_key]
    db.add(PushLog(slot=slot, category_slug="all", item_ids=all_ids))
    db.commit()
    logger.info("Pushed %d featured + %d key items for slot=%s", len(featured), len(new_key), slot)
    return True
