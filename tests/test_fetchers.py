import pytest
from unittest.mock import patch, MagicMock
from app.fetchers.base import RawItem
from app.fetchers.rss import RssFetcher
from app.config import SourceConfig
import respx
import httpx as _httpx


def make_rss_source(feed_url: str = "https://example.com/feed.rss") -> SourceConfig:
    return SourceConfig(name="Test RSS", fetch_type="rss",
                        feed_url=feed_url, enabled=True, extra={})


@pytest.fixture
def mock_feed():
    entry = MagicMock()
    entry.title = "测试标题"
    entry.link = "https://example.com/article/1"
    entry.summary = "这是文章摘要内容。"
    entry.published_parsed = (2026, 6, 8, 9, 0, 0, 6, 159, 0)
    feed = MagicMock()
    feed.entries = [entry]
    feed.bozo = False
    return feed


@pytest.mark.asyncio
async def test_rss_returns_items(mock_feed):
    with patch("feedparser.parse", return_value=mock_feed):
        items = await RssFetcher(make_rss_source()).fetch()
    assert len(items) == 1
    assert items[0].title == "测试标题"
    assert items[0].url == "https://example.com/article/1"


@pytest.mark.asyncio
async def test_rss_skips_empty_title(mock_feed):
    mock_feed.entries[0].title = ""
    with patch("feedparser.parse", return_value=mock_feed):
        items = await RssFetcher(make_rss_source()).fetch()
    assert len(items) == 0


@pytest.mark.asyncio
async def test_rss_handles_bozo_error():
    broken = MagicMock()
    broken.bozo = True
    broken.bozo_exception = Exception("parse error")
    broken.entries = []
    with patch("feedparser.parse", return_value=broken):
        items = await RssFetcher(make_rss_source()).fetch()
    assert items == []


# ── GitHub ────────────────────────────────────────────────────────────────────
from app.fetchers.api_github import GithubFetcher

GITHUB_RESPONSE = {"items": [{
    "full_name": "owner/cool-repo",
    "html_url": "https://github.com/owner/cool-repo",
    "description": "A cool AI agent framework",
    "stargazers_count": 5000,
    "language": "Python",
}]}


@respx.mock
@pytest.mark.asyncio
async def test_github_fetcher_returns_items():
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=_httpx.Response(200, json=GITHUB_RESPONSE)
    )
    src = SourceConfig(name="GH", fetch_type="api_github",
                       feed_url="https://api.github.com/search/repositories",
                       enabled=True, extra={"topics": ["ai"], "per_page": 1})
    items = await GithubFetcher(src).fetch()
    assert len(items) == 1
    assert "cool-repo" in items[0].title
    assert items[0].extra["stars"] == 5000


# ── Hacker News ───────────────────────────────────────────────────────────────
from app.fetchers.api_hn import HNFetcher

HN_STORY = {"id": 1, "title": "Show HN: My AI Tool",
             "url": "https://example.com/tool", "score": 200,
             "by": "user1", "type": "story"}
HN_ASK = {"id": 2, "title": "Ask HN: Best frameworks?",
           "score": 100, "by": "user2", "type": "story"}


@respx.mock
@pytest.mark.asyncio
async def test_hn_fetcher_returns_items():
    base = "https://hacker-news.firebaseio.com/v0"
    respx.get(f"{base}/topstories.json").mock(
        return_value=_httpx.Response(200, json=[1, 2]))
    respx.get(f"{base}/item/1.json").mock(
        return_value=_httpx.Response(200, json=HN_STORY))
    respx.get(f"{base}/item/2.json").mock(
        return_value=_httpx.Response(200, json=HN_ASK))
    src = SourceConfig(name="HN", fetch_type="api_hn", feed_url=base,
                       enabled=True, extra={"story_type": "top", "limit": 2})
    items = await HNFetcher(src).fetch()
    assert len(items) == 2
    assert items[0].url == "https://example.com/tool"
    assert "ycombinator" in items[1].url or "hacker-news" in items[1].url


@respx.mock
@pytest.mark.asyncio
async def test_hn_show_filter():
    base = "https://hacker-news.firebaseio.com/v0"
    respx.get(f"{base}/showstories.json").mock(
        return_value=_httpx.Response(200, json=[1]))
    respx.get(f"{base}/item/1.json").mock(
        return_value=_httpx.Response(200, json=HN_STORY))
    src = SourceConfig(name="HN Show", fetch_type="api_hn", feed_url=base,
                       enabled=True, extra={"story_type": "show", "limit": 1})
    items = await HNFetcher(src).fetch()
    assert len(items) == 1


# ── Registry ──────────────────────────────────────────────────────────────────
from app.fetchers.registry import get_fetcher
from app.fetchers.rss import RssFetcher
from app.fetchers.api_github import GithubFetcher


def test_registry_correct_class():
    rss = make_rss_source()
    gh = SourceConfig(name="GH", fetch_type="api_github",
                      feed_url="https://api.github.com", enabled=True, extra={})
    assert isinstance(get_fetcher(rss), RssFetcher)
    assert isinstance(get_fetcher(gh), GithubFetcher)


def test_registry_unknown_raises():
    bad = SourceConfig(name="X", fetch_type="unknown",
                       feed_url="https://x.com", enabled=True, extra={})
    with pytest.raises(ValueError, match="Unknown fetch_type"):
        get_fetcher(bad)
