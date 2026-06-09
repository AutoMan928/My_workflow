"""
Scrapes github.com/trending for the fastest star-gaining repositories today.
"""
import logging
import re
import httpx
from app.fetchers.base import BaseFetcher, RawItem

logger = logging.getLogger(__name__)

_TRENDING_URL = "https://github.com/trending"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_RE_ARTICLE = re.compile(
    r'<article[^>]+class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>',
    re.DOTALL,
)
_RE_REPO_HREF = re.compile(
    r'<a\s[^>]*href="/([a-zA-Z0-9_.\-]+/[a-zA-Z0-9_.\-]+)"',
    re.DOTALL,
)
_RE_DESC = re.compile(
    r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>\s*(.*?)\s*</p>',
    re.DOTALL,
)
_RE_STARS_TODAY = re.compile(
    r'float-sm-right[^>]*>.*?([\d,]+)\s+stars?\s+today',
    re.DOTALL,
)
_RE_LANG = re.compile(r'itemprop="programmingLanguage">([^<]+)<')
_RE_TAGS = re.compile(r'<[^>]+>')
_RE_WS = re.compile(r'\s+')


class GitHubTrendingFetcher(BaseFetcher):
    """Scrapes GitHub Trending for fastest-rising repositories."""

    async def fetch(self) -> list[RawItem]:
        since = self.source.extra.get("since", "daily")
        limit = self.source.extra.get("limit", 20)

        try:
            async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=True) as client:
                resp = await client.get(
                    _TRENDING_URL,
                    params={"since": since},
                    headers=_HEADERS,
                )
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            logger.error("GitHub trending fetch failed: %s", exc)
            return []

        items: list[RawItem] = []
        for m in _RE_ARTICLE.finditer(html):
            article = m.group(1)

            repo_path: str | None = None
            for link_m in _RE_REPO_HREF.finditer(article):
                candidate = link_m.group(1)
                if candidate.count("/") == 1:
                    repo_path = candidate
                    break
            if not repo_path:
                continue

            desc = ""
            desc_m = _RE_DESC.search(article)
            if desc_m:
                desc = _RE_TAGS.sub("", desc_m.group(1)).strip()
                desc = _RE_WS.sub(" ", desc)

            stars_today = 0
            stars_m = _RE_STARS_TODAY.search(article)
            if stars_m:
                try:
                    stars_today = int(stars_m.group(1).replace(",", ""))
                except ValueError:
                    pass

            lang = ""
            lang_m = _RE_LANG.search(article)
            if lang_m:
                lang = lang_m.group(1).strip()

            items.append(RawItem(
                title=repo_path,
                url=f"https://github.com/{repo_path}",
                raw_text=desc,
                extra={
                    "stars_today": stars_today,
                    "stars": stars_today,
                    "language": lang,
                    "description": desc,
                },
            ))

        items.sort(key=lambda x: x.extra.get("stars_today", 0), reverse=True)
        logger.info("GitHub trending: fetched %d repos (since=%s)", len(items[:limit]), since)
        return items[:limit]
