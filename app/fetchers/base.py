from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from app.config import SourceConfig


@dataclass
class RawItem:
    title: str
    url: str
    raw_text: str = ""
    published_at: datetime | None = None
    extra: dict = field(default_factory=dict)


class BaseFetcher(ABC):
    def __init__(self, source: SourceConfig) -> None:
        self.source = source

    @abstractmethod
    async def fetch(self) -> list:
        ...
