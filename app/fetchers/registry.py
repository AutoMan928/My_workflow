from app.config import SourceConfig
from app.fetchers.base import BaseFetcher
from app.fetchers.rss import RssFetcher
from app.fetchers.api_github import GithubFetcher
from app.fetchers.api_hn import HNFetcher
from app.fetchers.api_ph import ProductHuntFetcher
from app.fetchers.api_hf import HuggingFaceFetcher
from app.fetchers.scraper import ScraperFetcher

REGISTRY: dict[str, type[BaseFetcher]] = {
    "rss": RssFetcher,
    "api_github": GithubFetcher,
    "api_hn": HNFetcher,
    "api_ph": ProductHuntFetcher,
    "api_hf": HuggingFaceFetcher,
    "scraper": ScraperFetcher,
}


def get_fetcher(source: SourceConfig) -> BaseFetcher:
    cls = REGISTRY.get(source.fetch_type)
    if cls is None:
        raise ValueError(
            f"Unknown fetch_type: {source.fetch_type!r}. Available: {list(REGISTRY)}"
        )
    return cls(source)
