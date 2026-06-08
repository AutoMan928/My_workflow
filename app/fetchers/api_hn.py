import asyncio
import logging
import httpx
from typing import Optional
from app.fetchers.base import BaseFetcher, RawItem

logger = logging.getLogger(__name__)

STORY_TYPE_MAP = {
    "top": "topstories", "new": "newstories",
    "show": "showstories", "ask": "askstories",
}


class HNFetcher(BaseFetcher):
    async def fetch(self) -> list:
        base = self.source.feed_url.rstrip("/")
        story_type = self.source.extra.get("story_type", "top")
        limit = self.source.extra.get("limit", 30)
        endpoint = STORY_TYPE_MAP.get(story_type, "topstories")

        try:
            async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
                resp = await client.get(f"{base}/{endpoint}.json")
                resp.raise_for_status()
                story_ids = resp.json()[:limit]

                stories = await asyncio.gather(
                    *[client.get(f"{base}/item/{sid}.json") for sid in story_ids],
                    return_exceptions=True,
                )
        except Exception as exc:
            logger.error("HN fetch failed: %s", exc)
            return []

        items: list = []
        for result in stories:
            if isinstance(result, Exception):
                logger.warning("HN item fetch failed: %s", result)
                continue
            story = result.json()
            title = story.get("title", "").strip()
            if not title or story.get("type") != "story":
                continue
            url = (story.get("url")
                   or f"https://news.ycombinator.com/item?id={story['id']}")
            items.append(RawItem(
                title=title, url=url,
                raw_text=story.get("text", ""),
                extra={"score": story.get("score", 0), "by": story.get("by", "")},
            ))
        return items
