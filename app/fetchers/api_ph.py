from app.fetchers.rss import RssFetcher


class ProductHuntFetcher(RssFetcher):
    """Product Hunt 通过其公开 RSS feed 抓取，直接复用 RssFetcher。"""
    pass
