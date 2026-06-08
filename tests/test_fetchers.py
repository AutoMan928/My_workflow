import pytest
from unittest.mock import patch, MagicMock
from app.fetchers.base import RawItem
from app.fetchers.rss import RssFetcher
from app.config import SourceConfig


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
