import logging
from urllib.parse import urlparse, urljoin
from app.fetchers.base import BaseFetcher, RawItem

logger = logging.getLogger(__name__)

MAX_SCRAPE_LINKS = 20
SCRAPE_TIMEOUT_MS = 30000


class ScraperFetcher(BaseFetcher):
    async def fetch(self) -> list:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "playwright not installed. Run: pip install 'news-platform[scraper]' && playwright install chromium"
            )
            return []

        selector = self.source.extra.get("selector", "a")
        items: list = []

        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(self.source.feed_url, timeout=SCRAPE_TIMEOUT_MS)
                links = await page.query_selector_all(selector)
                for link in links[:MAX_SCRAPE_LINKS]:
                    title = (await link.inner_text()).strip()
                    href = await link.get_attribute("href") or ""
                    if not title or not href:
                        continue
                    href = urljoin(self.source.feed_url, href)
                    items.append(RawItem(title=title, url=href))
            except Exception as exc:
                logger.error("Scraper failed for %s: %s", self.source.name, exc)
            finally:
                if browser:
                    await browser.close()
        return items
