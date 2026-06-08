import logging
import os
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.push_log import PushLog

logger = logging.getLogger(__name__)

_SLOT_LABELS = {"morning": "早间", "evening": "晚间"}
_CAT_LABELS = {"banking": "银行用户运营", "tech": "技术与AI工具", "startup": "个人创业"}


def _build_card(slot: str, items_by_cat: dict[str, list[Item]]) -> dict:
    date_str = datetime.now().strftime("%Y-%m-%d")
    slot_label = _SLOT_LABELS.get(slot, slot)
    elements = []
    for cat_slug, items in items_by_cat.items():
        if not items:
            continue
        elements.append({"tag": "markdown",
                          "content": f"**{_CAT_LABELS.get(cat_slug, cat_slug)}**"})
        for item in items:
            summary = (item.summary_zh or item.title)[:100]
            suffix = ""
            if item.ai_extra and "fit_score" in item.ai_extra:
                suffix = f" | 适合度 {item.ai_extra['fit_score']:.1f}"
            elements.append({"tag": "markdown",
                              "content": f"• [{item.title}]({item.url})\n  {summary}{suffix}"})
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text",
                          "content": f"📰 资讯速报 · {date_str} {slot_label}"},
                "template": "blue",
            },
            "elements": elements,
        },
    }


def push_key_items(
    slot: str,
    items: list[Item],
    db: Session,
    webhook_url: str | None = None,
    dry_run: bool = False,
) -> bool:
    if not items:
        return True

    pushed_ids: set[int] = set()
    for log in db.query(PushLog).filter_by(slot=slot).all():
        pushed_ids.update(log.item_ids)

    new_items = [i for i in items if i.id not in pushed_ids]
    if not new_items:
        logger.info("All key items already pushed for slot=%s", slot)
        return True

    items_by_cat: dict[str, list[Item]] = {}
    for item in new_items:
        items_by_cat.setdefault(item.category_slug, []).append(item)

    if dry_run:
        logger.info("[dry-run] Would push %d items to Feishu", len(new_items))
        return True

    url = webhook_url or os.environ.get("FEISHU_WEBHOOK_URL")
    if not url:
        raise ValueError("FEISHU_WEBHOOK_URL not set")

    try:
        resp = httpx.post(url, json=_build_card(slot, items_by_cat), timeout=10)
        resp.raise_for_status()
        if resp.json().get("code") != 0:
            logger.error("Feishu error: %s", resp.json())
            return False
    except Exception as exc:
        logger.error("Feishu push failed: %s", exc)
        return False

    db.add(PushLog(slot=slot, category_slug="all",
                   item_ids=[i.id for i in new_items]))
    db.commit()
    logger.info("Pushed %d key items to Feishu for slot=%s", len(new_items), slot)
    return True
