import logging
import httpx
from typing import List
from app.fetchers.base import BaseFetcher, RawItem

logger = logging.getLogger(__name__)


class GithubFetcher(BaseFetcher):
    async def fetch(self) -> List[RawItem]:
        topics: List[str] = self.source.extra.get("topics", ["ai", "agent", "llm"])
        per_page: int = self.source.extra.get("per_page", 20)
        query = " ".join(f"topic:{t}" for t in topics) + " sort:stars"

        try:
            async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
                resp = await client.get(
                    self.source.feed_url,
                    params={"q": query, "sort": "stars", "order": "desc",
                            "per_page": per_page},
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("GitHub fetch failed: %s", exc)
            return []

        items: List[RawItem] = []
        for repo in data.get("items", []):
            name = repo.get("full_name", "")
            url = repo.get("html_url", "")
            desc = repo.get("description") or ""
            if not name or not url:
                continue
            items.append(RawItem(
                title=name, url=url, raw_text=desc,
                extra={"stars": repo.get("stargazers_count", 0),
                       "language": repo.get("language") or "",
                       "description": desc},
            ))
        return items
