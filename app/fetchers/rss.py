import asyncio
import logging
from datetime import datetime
from time import mktime, struct_time

import feedparser

from app.fetchers.base import BaseFetcher, RawItem

logger = logging.getLogger(__name__)


def _parse_time(t: struct_time | None) -> datetime | None:
    if t is None:
        return None
    try:
        return datetime.fromtimestamp(mktime(t))
    except (ValueError, OverflowError):
        return None


class RssFetcher(BaseFetcher):
    async def fetch(self) -> list:
        try:
            feed = await asyncio.to_thread(feedparser.parse, self.source.feed_url)
        except Exception as exc:
            logger.error("RSS fetch failed for %s: %s", self.source.name, exc)
            return []

        if feed.bozo and not feed.entries:
            logger.warning("Bozo feed %s: %s", self.source.name, feed.bozo_exception)
            return []

        items: list = []
        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            url = getattr(entry, "link", "").strip()
            if not title or not url:
                continue
            raw_text = (
                getattr(entry, "summary", "")
                or (getattr(entry, "content", [{}])[0].get("value", ""))
            )
            items.append(RawItem(
                title=title,
                url=url,
                raw_text=raw_text,
                published_at=_parse_time(getattr(entry, "published_parsed", None)),
            ))
        return items
