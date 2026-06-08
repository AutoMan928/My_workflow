# 个人资讯平台 · 核心数据管道实现计划（Plan 1）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建完整的数据采集管道——从多源抓取、去重、AI 分级处理到 SQLite 存储和飞书推送，通过 CLI 入口 `python -m app.run --slot morning` 触发，支持 `--dry-run` 模式（不调用真实 Claude API）。

**Architecture:** 同步 SQLAlchemy（SQLite）管理数据，asyncio + httpx 并发抓取多个源，Anthropic SDK 分级处理（Haiku 处理轻/中类别，Sonnet 处理深度类别），系统 cron 触发 CLI。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, feedparser, httpx, anthropic SDK, pydantic 2, PyYAML, itsdangerous, pytest, respx

---

## 文件清单

```
news-platform/
├── pyproject.toml
├── .env.example
├── .gitignore
├── config.yaml
├── crontab.example
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app + /health
│   ├── run.py                     # CLI 入口
│   ├── config.py                  # 读 config.yaml，替换 {ENV_VAR} 占位符
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                # Engine + SessionLocal + Base + init_db
│   │   ├── item.py                # Item ORM
│   │   ├── source.py              # SourceRecord ORM（运行时跟踪）
│   │   ├── push_log.py            # PushLog ORM
│   │   └── run_log.py             # RunLog ORM
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── base.py                # RawItem dataclass + BaseFetcher ABC
│   │   ├── rss.py                 # feedparser，覆盖 RSS + RSSHub
│   │   ├── api_github.py          # GitHub Search API
│   │   ├── api_hn.py              # Hacker News Firebase API
│   │   ├── api_ph.py              # Product Hunt（复用 RssFetcher）
│   │   ├── api_hf.py              # HuggingFace API
│   │   ├── scraper.py             # playwright 兜底
│   │   └── registry.py            # fetch_type → fetcher class
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── client.py              # Anthropic SDK 封装，dry-run 支持
│   │   ├── schemas.py             # BankingResult / TechResult / StartupResult
│   │   ├── banking.py             # 类1 处理器
│   │   ├── tech.py                # 类2 处理器
│   │   ├── startup.py             # 类3 处理器
│   │   └── processor.py           # depth_level → 处理器路由
│   ├── push/
│   │   ├── __init__.py
│   │   └── feishu.py              # 飞书 webhook + push_log 去重
│   └── scheduler/
│       ├── __init__.py
│       ├── dedup.py               # compute_hash + filter_new_items
│       └── pipeline.py            # 主流程：fetch→dedup→AI→save→push
└── tests/
    ├── __init__.py
    ├── conftest.py                # pytest fixtures
    ├── test_config.py
    ├── test_models.py
    ├── test_fetchers.py
    ├── test_dedup.py
    ├── test_ai.py
    └── test_pipeline.py
```

---

## Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: all `__init__.py` files

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "news-platform"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy>=2.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    "pyyaml>=6.0.0",
    "feedparser>=6.0.11",
    "httpx>=0.27.0",
    "anthropic>=0.28.0",
    "itsdangerous>=2.2.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "respx>=0.21.0",
]
scraper = [
    "playwright>=1.44.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: 创建 .env.example**

```
ANTHROPIC_API_KEY=your-key-here
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your-token
SITE_PASSWORD=changeme
RSSHUB_BASE_URL=http://localhost:1200
DATABASE_URL=sqlite:///data/news.db
```

- [ ] **Step 3: 创建 .gitignore**

```
.env
data/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
.venv/
venv/
```

- [ ] **Step 4: 创建目录结构和空 __init__.py**

```bash
mkdir -p app/models app/fetchers app/ai app/push app/scheduler tests data
touch app/__init__.py app/models/__init__.py app/fetchers/__init__.py \
      app/ai/__init__.py app/push/__init__.py app/scheduler/__init__.py \
      tests/__init__.py
echo "data/" >> .gitignore
```

- [ ] **Step 5: 安装依赖**

```bash
pip install -e ".[dev]"
```

Expected: `Successfully installed news-platform-0.1.0 ...`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example .gitignore app/ tests/
git commit -m "chore: project scaffold"
```

---

## Task 2: 配置模块

**Files:**
- Create: `config.yaml`
- Create: `app/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 先写失败的测试**

`tests/test_config.py`:
```python
import pytest
from app.config import load_config, _substitute_env_vars

MINIMAL_CONFIG = """
settings:
  dedup_days: 7
  db_path: data/news.db
  timezone: Asia/Shanghai
categories:
  - name: 测试类别
    slug: test
    depth_level: medium
    schedule: [morning]
    enabled: true
    importance_rule:
      is_key_threshold: 7.0
      boost_tags: []
    sources:
      - name: 测试源
        fetch_type: rss
        feed_url: "http://{TEST_HOST}/feed"
        enabled: true
        extra: {}
"""


def test_substitute_env_vars(monkeypatch):
    monkeypatch.setenv("TEST_HOST", "example.com")
    assert _substitute_env_vars("http://{TEST_HOST}/feed") == "http://example.com/feed"


def test_missing_env_var_keeps_placeholder():
    result = _substitute_env_vars("http://{UNDEFINED_VAR}/feed")
    assert result == "http://{UNDEFINED_VAR}/feed"


def test_load_config(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_HOST", "rsshub:1200")
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(MINIMAL_CONFIG)
    cfg = load_config(str(cfg_file))
    assert cfg.settings.dedup_days == 7
    assert len(cfg.categories) == 1
    assert cfg.categories[0].slug == "test"
    assert cfg.categories[0].sources[0].feed_url == "http://rsshub:1200/feed"


def test_category_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_HOST", "localhost:1200")
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(MINIMAL_CONFIG)
    cfg = load_config(str(cfg_file))
    src = cfg.categories[0].sources[0]
    assert src.fetch_type == "rss"
    assert src.enabled is True
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_config.py -v
```

Expected: `FAILED` (ImportError)

- [ ] **Step 3: 实现 app/config.py**

```python
import os
import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel


class ImportanceRule(BaseModel):
    is_key_threshold: float
    boost_tags: list[str] = []


class SourceConfig(BaseModel):
    name: str
    fetch_type: str
    feed_url: str
    enabled: bool = True
    extra: dict = {}


class CategoryConfig(BaseModel):
    name: str
    slug: str
    depth_level: str
    schedule: list[str]
    importance_rule: ImportanceRule
    sources: list[SourceConfig]
    enabled: bool = True


class Settings(BaseModel):
    dedup_days: int = 7
    db_path: str = "data/news.db"
    timezone: str = "Asia/Shanghai"


class AppConfig(BaseModel):
    settings: Settings
    categories: list[CategoryConfig]


def _substitute_env_vars(text: str) -> str:
    def replacer(match: re.Match) -> str:
        var = match.group(1)
        return os.environ.get(var, f"{{{var}}}")
    return re.sub(r"\{([A-Z_][A-Z0-9_]*)\}", replacer, text)


def load_config(path: str = "config.yaml") -> AppConfig:
    raw = Path(path).read_text(encoding="utf-8")
    substituted = _substitute_env_vars(raw)
    data = yaml.safe_load(substituted)
    return AppConfig(**data)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return load_config()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_config.py -v
```

Expected: 4 passed

- [ ] **Step 5: 创建 config.yaml（初始种子）**

```yaml
settings:
  dedup_days: 7
  db_path: data/news.db
  timezone: Asia/Shanghai

categories:
  - name: 银行用户运营
    slug: banking
    depth_level: medium_deep
    schedule: [morning, evening]
    enabled: true
    importance_rule:
      is_key_threshold: 7.0
      boost_tags: [业务方案, 方法论, 监管政策, 竞品动态]
    sources:
      - name: 艾瑞咨询
        fetch_type: rss
        feed_url: "http://{RSSHUB_BASE_URL}/iresearch/report"
        enabled: true
        extra: {}
      - name: 36氪·金融
        fetch_type: rss
        feed_url: "http://{RSSHUB_BASE_URL}/36kr/newsflashes"
        enabled: true
        extra: {}
      - name: 零壹财经
        fetch_type: rss
        feed_url: "http://{RSSHUB_BASE_URL}/01caijing/articles"
        enabled: true
        extra: {}
      - name: 亿欧·金融科技
        fetch_type: rss
        feed_url: "http://{RSSHUB_BASE_URL}/iyiou/fintech"
        enabled: true
        extra: {}
      - name: 央行官网
        fetch_type: scraper
        feed_url: "http://www.pbc.gov.cn/goutongjiaoliu/113456/index.html"
        enabled: false
        extra: {selector: ".newsList li"}

  - name: 技术与AI工具
    slug: tech
    depth_level: medium
    schedule: [morning]
    enabled: true
    importance_rule:
      is_key_threshold: 7.5
      boost_tags: []
    sources:
      - name: GitHub Trending (AI)
        fetch_type: api_github
        feed_url: "https://api.github.com/search/repositories"
        enabled: true
        extra:
          topics: [ai, agent, llm]
          period: daily
          per_page: 20
      - name: Hacker News
        fetch_type: api_hn
        feed_url: "https://hacker-news.firebaseio.com/v0"
        enabled: true
        extra:
          story_type: top
          limit: 30
      - name: Product Hunt
        fetch_type: api_ph
        feed_url: "https://www.producthunt.com/feed"
        enabled: true
        extra: {}
      - name: Hugging Face Trending
        fetch_type: api_hf
        feed_url: "https://huggingface.co/api"
        enabled: true
        extra: {}
      - name: 机器之心
        fetch_type: rss
        feed_url: "http://{RSSHUB_BASE_URL}/jiqizhixin"
        enabled: true
        extra: {}
      - name: 量子位
        fetch_type: rss
        feed_url: "http://{RSSHUB_BASE_URL}/qbitai"
        enabled: true
        extra: {}

  - name: 个人创业
    slug: startup
    depth_level: deep
    schedule: [morning]
    enabled: true
    importance_rule:
      is_key_threshold: 6.5
      boost_tags: []
    sources:
      - name: IndieHackers
        fetch_type: rss
        feed_url: "https://www.indiehackers.com/feed.rss"
        enabled: true
        extra: {}
      - name: Product Hunt (Startup)
        fetch_type: api_ph
        feed_url: "https://www.producthunt.com/feed"
        enabled: true
        extra: {view: startup}
      - name: 36氪·创投
        fetch_type: rss
        feed_url: "http://{RSSHUB_BASE_URL}/36kr/venture"
        enabled: true
        extra: {}
      - name: Hacker News Show HN
        fetch_type: api_hn
        feed_url: "https://hacker-news.firebaseio.com/v0"
        enabled: true
        extra:
          story_type: show
          limit: 20
```

- [ ] **Step 6: Commit**

```bash
git add app/config.py config.yaml tests/test_config.py
git commit -m "feat: config loading with env var substitution"
```

---

## Task 3: 数据库模型

**Files:**
- Create: `app/models/base.py`
- Create: `app/models/item.py`
- Create: `app/models/source.py`
- Create: `app/models/push_log.py`
- Create: `app/models/run_log.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: 先写失败的测试**

`tests/test_models.py`:
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.item import Item
from app.models.push_log import PushLog
from app.models.run_log import RunLog


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_item(db):
    item = Item(source_id=1, category_slug="banking",
                title="测试标题", url="https://example.com/1",
                dedup_hash="abc123")
    db.add(item)
    db.commit()
    found = db.query(Item).filter_by(dedup_hash="abc123").first()
    assert found.title == "测试标题"
    assert found.is_read is False
    assert found.is_key is False


def test_item_url_unique(db):
    from sqlalchemy.exc import IntegrityError
    db.add(Item(source_id=1, category_slug="banking", title="A",
                url="https://example.com/dup", dedup_hash="hash1"))
    db.commit()
    db.add(Item(source_id=1, category_slug="banking", title="B",
                url="https://example.com/dup", dedup_hash="hash2"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_create_push_log(db):
    log = PushLog(slot="morning", category_slug="banking", item_ids=[1, 2, 3])
    db.add(log)
    db.commit()
    found = db.query(PushLog).first()
    assert found.item_ids == [1, 2, 3]


def test_create_run_log(db):
    log = RunLog(slot="morning", category_slug="banking",
                 status="success", items_fetched=10, items_new=3)
    db.add(log)
    db.commit()
    found = db.query(RunLog).filter_by(status="success").first()
    assert found.items_new == 3
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_models.py -v
```

Expected: `FAILED` (ImportError)

- [ ] **Step 3: 实现 app/models/base.py**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/news.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from app.models import item, push_log, run_log, source  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: 实现 app/models/item.py**

```python
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    category_slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    summary_zh: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)
    is_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_extra: Mapped[dict | None] = mapped_column(JSON)
    content_tag: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    dedup_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

- [ ] **Step 5: 实现 app/models/source.py**

```python
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class SourceRecord(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    fetch_type: Mapped[str] = mapped_column(String(32), nullable=False)
    feed_url: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
```

- [ ] **Step 6: 实现 app/models/push_log.py**

```python
from datetime import datetime
from sqlalchemy import DateTime, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class PushLog(Base):
    __tablename__ = "push_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot: Mapped[str] = mapped_column(String(16), nullable=False)
    category_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    pushed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    item_ids: Mapped[list] = mapped_column(JSON, nullable=False)
```

- [ ] **Step 7: 实现 app/models/run_log.py**

```python
from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class RunLog(Base):
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot: Mapped[str] = mapped_column(String(16), nullable=False)
    category_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    items_fetched: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 8: 运行测试，确认通过**

```bash
pytest tests/test_models.py -v
```

Expected: 4 passed

- [ ] **Step 9: Commit**

```bash
git add app/models/ tests/test_models.py
git commit -m "feat: SQLAlchemy models (item, source, push_log, run_log)"
```

---

## Task 4: Fetcher 基础类 + RSS Fetcher

**Files:**
- Create: `app/fetchers/base.py`
- Create: `app/fetchers/rss.py`
- Test: `tests/test_fetchers.py`

- [ ] **Step 1: 先写失败的测试**

`tests/test_fetchers.py`:
```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_fetchers.py -v
```

Expected: `FAILED` (ImportError)

- [ ] **Step 3: 实现 app/fetchers/base.py**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawItem:
    title: str
    url: str
    raw_text: str = ""
    published_at: datetime | None = None
    extra: dict = field(default_factory=dict)


class BaseFetcher(ABC):
    def __init__(self, source):
        self.source = source

    @abstractmethod
    async def fetch(self) -> list[RawItem]:
        ...
```

- [ ] **Step 4: 实现 app/fetchers/rss.py**

```python
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
    async def fetch(self) -> list[RawItem]:
        try:
            feed = await asyncio.to_thread(feedparser.parse, self.source.feed_url)
        except Exception as exc:
            logger.error("RSS fetch failed for %s: %s", self.source.name, exc)
            return []

        if feed.bozo and not feed.entries:
            logger.warning("Bozo feed %s: %s", self.source.name, feed.bozo_exception)
            return []

        items: list[RawItem] = []
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
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
pytest tests/test_fetchers.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add app/fetchers/base.py app/fetchers/rss.py tests/test_fetchers.py
git commit -m "feat: RawItem dataclass + RSS fetcher"
```

---

## Task 5: GitHub + HN API Fetchers

**Files:**
- Create: `app/fetchers/api_github.py`
- Create: `app/fetchers/api_hn.py`
- Test: `tests/test_fetchers.py`（追加）

- [ ] **Step 1: 追加 GitHub + HN 测试到 tests/test_fetchers.py**

在文件末尾追加：
```python
import respx
import httpx as _httpx

# ── GitHub ────────────────────────────────────────────────────────────────────
from app.fetchers.api_github import GithubFetcher

GITHUB_RESPONSE = {"items": [{
    "full_name": "owner/cool-repo",
    "html_url": "https://github.com/owner/cool-repo",
    "description": "A cool AI agent framework",
    "stargazers_count": 5000,
    "language": "Python",
}]}


@pytest.mark.asyncio
async def test_github_fetcher_returns_items():
    src = SourceConfig(name="GH", fetch_type="api_github",
                       feed_url="https://api.github.com/search/repositories",
                       enabled=True, extra={"topics": ["ai"], "per_page": 1})
    with respx.mock:
        respx.get("https://api.github.com/search/repositories").mock(
            return_value=_httpx.Response(200, json=GITHUB_RESPONSE)
        )
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


@pytest.mark.asyncio
async def test_hn_fetcher_returns_items():
    base = "https://hacker-news.firebaseio.com/v0"
    src = SourceConfig(name="HN", fetch_type="api_hn", feed_url=base,
                       enabled=True, extra={"story_type": "top", "limit": 2})
    with respx.mock:
        respx.get(f"{base}/topstories.json").mock(
            return_value=_httpx.Response(200, json=[1, 2]))
        respx.get(f"{base}/item/1.json").mock(
            return_value=_httpx.Response(200, json=HN_STORY))
        respx.get(f"{base}/item/2.json").mock(
            return_value=_httpx.Response(200, json=HN_ASK))
        items = await HNFetcher(src).fetch()
    assert len(items) == 2
    assert items[0].url == "https://example.com/tool"
    assert "ycombinator" in items[1].url or "hacker-news" in items[1].url


@pytest.mark.asyncio
async def test_hn_show_filter():
    base = "https://hacker-news.firebaseio.com/v0"
    src = SourceConfig(name="HN Show", fetch_type="api_hn", feed_url=base,
                       enabled=True, extra={"story_type": "show", "limit": 1})
    with respx.mock:
        respx.get(f"{base}/showstories.json").mock(
            return_value=_httpx.Response(200, json=[1]))
        respx.get(f"{base}/item/1.json").mock(
            return_value=_httpx.Response(200, json=HN_STORY))
        items = await HNFetcher(src).fetch()
    assert len(items) == 1
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_fetchers.py::test_github_fetcher_returns_items -v
```

Expected: `FAILED` (ImportError)

- [ ] **Step 3: 实现 app/fetchers/api_github.py**

```python
import logging
import httpx
from app.fetchers.base import BaseFetcher, RawItem

logger = logging.getLogger(__name__)


class GithubFetcher(BaseFetcher):
    async def fetch(self) -> list[RawItem]:
        topics: list[str] = self.source.extra.get("topics", ["ai", "agent", "llm"])
        per_page: int = self.source.extra.get("per_page", 20)
        query = " ".join(f"topic:{t}" for t in topics) + " sort:stars"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
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

        items: list[RawItem] = []
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
```

- [ ] **Step 4: 实现 app/fetchers/api_hn.py**

```python
import asyncio
import logging
import httpx
from app.fetchers.base import BaseFetcher, RawItem

logger = logging.getLogger(__name__)

STORY_TYPE_MAP = {
    "top": "topstories", "new": "newstories",
    "show": "showstories", "ask": "askstories",
}


class HNFetcher(BaseFetcher):
    async def fetch(self) -> list[RawItem]:
        base = self.source.feed_url.rstrip("/")
        story_type = self.source.extra.get("story_type", "top")
        limit = self.source.extra.get("limit", 30)
        endpoint = STORY_TYPE_MAP.get(story_type, "topstories")

        try:
            async with httpx.AsyncClient(timeout=15) as client:
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

        items: list[RawItem] = []
        for result in stories:
            if isinstance(result, Exception):
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
```

- [ ] **Step 5: 运行全部 fetcher 测试**

```bash
pytest tests/test_fetchers.py -v
```

Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add app/fetchers/api_github.py app/fetchers/api_hn.py tests/test_fetchers.py
git commit -m "feat: GitHub + HN API fetchers"
```

---

## Task 6: PH / HF / Scraper Fetchers + Registry

**Files:**
- Create: `app/fetchers/api_ph.py`
- Create: `app/fetchers/api_hf.py`
- Create: `app/fetchers/scraper.py`
- Create: `app/fetchers/registry.py`

- [ ] **Step 1: 实现 app/fetchers/api_ph.py**

```python
from app.fetchers.rss import RssFetcher


class ProductHuntFetcher(RssFetcher):
    """Product Hunt 通过其公开 RSS feed 抓取，直接复用 RssFetcher。"""
    pass
```

- [ ] **Step 2: 实现 app/fetchers/api_hf.py**

```python
import logging
import httpx
from app.fetchers.base import BaseFetcher, RawItem

logger = logging.getLogger(__name__)


class HuggingFaceFetcher(BaseFetcher):
    async def fetch(self) -> list[RawItem]:
        base = self.source.feed_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{base}/models",
                    params={"sort": "trending", "limit": 20, "direction": -1},
                )
                resp.raise_for_status()
                models = resp.json()
        except Exception as exc:
            logger.error("HuggingFace fetch failed: %s", exc)
            return []

        items: list[RawItem] = []
        for model in models:
            model_id = model.get("modelId") or model.get("id", "")
            if not model_id:
                continue
            url = f"https://huggingface.co/{model_id}"
            desc = model.get("cardData", {}).get("description", "") or ""
            items.append(RawItem(
                title=model_id, url=url, raw_text=desc,
                extra={"downloads": model.get("downloads", 0),
                       "likes": model.get("likes", 0)},
            ))
        return items
```

- [ ] **Step 3: 实现 app/fetchers/scraper.py**

```python
import logging
from urllib.parse import urlparse
from app.fetchers.base import BaseFetcher, RawItem

logger = logging.getLogger(__name__)


class ScraperFetcher(BaseFetcher):
    async def fetch(self) -> list[RawItem]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright not installed. Run: pip install 'news-platform[scraper]' && playwright install chromium")
            return []

        selector = self.source.extra.get("selector", "a")
        items: list[RawItem] = []
        parsed_base = urlparse(self.source.feed_url)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(self.source.feed_url, timeout=30000)
                links = await page.query_selector_all(selector)
                for link in links[:20]:
                    title = (await link.inner_text()).strip()
                    href = await link.get_attribute("href") or ""
                    if not title or not href:
                        continue
                    if href.startswith("/"):
                        href = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                    items.append(RawItem(title=title, url=href))
            except Exception as exc:
                logger.error("Scraper failed for %s: %s", self.source.name, exc)
            finally:
                await browser.close()
        return items
```

- [ ] **Step 4: 实现 app/fetchers/registry.py**

```python
from app.fetchers.base import BaseFetcher
from app.fetchers.rss import RssFetcher
from app.fetchers.api_github import GithubFetcher
from app.fetchers.api_hn import HNFetcher
from app.fetchers.api_ph import ProductHuntFetcher
from app.fetchers.api_hf import HuggingFaceFetcher
from app.fetchers.scraper import ScraperFetcher
from app.config import SourceConfig

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
```

- [ ] **Step 5: 追加 registry 测试到 tests/test_fetchers.py**

```python
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
```

- [ ] **Step 6: 运行全部 fetcher 测试**

```bash
pytest tests/test_fetchers.py -v
```

Expected: all passed

- [ ] **Step 7: Commit**

```bash
git add app/fetchers/ tests/test_fetchers.py
git commit -m "feat: PH/HF/scraper fetchers + registry"
```

---

## Task 7: 去重模块

**Files:**
- Create: `app/scheduler/dedup.py`
- Test: `tests/test_dedup.py`

- [ ] **Step 1: 先写失败的测试**

`tests/test_dedup.py`:
```python
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.item import Item
from app.fetchers.base import RawItem
from app.scheduler.dedup import compute_hash, filter_new_items


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_hash_normalizes_url():
    h1 = compute_hash("https://Example.COM/Article ")
    h2 = compute_hash("https://example.com/article")
    assert h1 == h2


def test_hash_is_64_chars():
    assert len(compute_hash("https://example.com")) == 64


def test_filter_excludes_existing(db):
    url = "https://example.com/old"
    db.add(Item(source_id=1, category_slug="banking", title="Old",
                url=url, dedup_hash=compute_hash(url),
                fetched_at=datetime.utcnow()))
    db.commit()
    raw = [RawItem(title="Old", url=url),
           RawItem(title="New", url="https://example.com/new")]
    new = filter_new_items(raw, db, dedup_days=7)
    assert len(new) == 1
    assert new[0].url == "https://example.com/new"
    assert new[0].extra["dedup_hash"] == compute_hash("https://example.com/new")


def test_filter_dedupes_within_batch(db):
    raw = [RawItem(title="A", url="https://example.com/a"),
           RawItem(title="A dup", url="https://example.com/a")]
    new = filter_new_items(raw, db, dedup_days=7)
    assert len(new) == 1


def test_old_items_not_considered(db):
    url = "https://example.com/very-old"
    db.add(Item(source_id=1, category_slug="banking", title="Old",
                url=url, dedup_hash=compute_hash(url),
                fetched_at=datetime.utcnow() - timedelta(days=10)))
    db.commit()
    new = filter_new_items([RawItem(title="Reappears", url=url)], db, dedup_days=7)
    assert len(new) == 1
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_dedup.py -v
```

Expected: `FAILED`

- [ ] **Step 3: 实现 app/scheduler/dedup.py**

```python
import hashlib
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.fetchers.base import RawItem
from app.models.item import Item


def compute_hash(url: str) -> str:
    normalized = url.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


def filter_new_items(
    raw_items: list[RawItem],
    db: Session,
    dedup_days: int = 7,
) -> list[RawItem]:
    cutoff = datetime.utcnow() - timedelta(days=dedup_days)
    existing: set[str] = {
        row[0]
        for row in db.query(Item.dedup_hash).filter(Item.fetched_at >= cutoff).all()
    }

    new_items: list[RawItem] = []
    seen: set[str] = set()
    for item in raw_items:
        h = compute_hash(item.url)
        if h not in existing and h not in seen:
            item.extra["dedup_hash"] = h
            new_items.append(item)
            seen.add(h)
    return new_items
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_dedup.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/scheduler/dedup.py tests/test_dedup.py
git commit -m "feat: dedup with 7-day sliding window"
```

---

## Task 8: AI Client + Schemas（dry-run 支持）

**Files:**
- Create: `app/ai/schemas.py`
- Create: `app/ai/client.py`
- Test: `tests/test_ai.py`

- [ ] **Step 1: 先写失败的测试**

`tests/test_ai.py`:
```python
import pytest
from app.ai.client import call_claude
from app.ai.schemas import BankingResult, TechResult, StartupResult


def test_dry_run_banking():
    raw = call_claude("any prompt", result_type="banking", dry_run=True)
    result = BankingResult.model_validate_json(raw)
    assert 0 <= result.score <= 10
    assert result.summary_zh


def test_dry_run_tech():
    raw = call_claude("any prompt", result_type="tech", dry_run=True)
    result = TechResult.model_validate_json(raw)
    assert 0 <= result.score <= 10


def test_dry_run_startup():
    raw = call_claude("any prompt", result_type="startup", dry_run=True)
    result = StartupResult.model_validate_json(raw)
    assert result.ai_extra.entry_advice
    assert result.ai_extra.fit_score is not None


def test_banking_schema_valid():
    r = BankingResult(summary_zh="摘要", score=8.5, is_key=True,
                      content_tag="监管政策类", work_impact="影响")
    assert r.is_key is True


def test_startup_schema_requires_ai_extra():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        StartupResult(summary_zh="test", score=7.0, is_key=True, ai_extra={})
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_ai.py -v
```

Expected: `FAILED`

- [ ] **Step 3: 实现 app/ai/schemas.py**

```python
from pydantic import BaseModel


class BankingResult(BaseModel):
    summary_zh: str
    score: float
    is_key: bool
    content_tag: str | None = None
    work_impact: str | None = None


class TechResult(BaseModel):
    summary_zh: str
    score: float
    is_key: bool


class StartupExtra(BaseModel):
    fit_score: float
    ai_approach: str
    monetization: str
    entry_advice: str


class StartupResult(BaseModel):
    summary_zh: str
    score: float
    is_key: bool
    ai_extra: StartupExtra
```

- [ ] **Step 4: 实现 app/ai/client.py**

```python
import json
import logging
import os
from typing import Literal

logger = logging.getLogger(__name__)

ResultType = Literal["banking", "tech", "startup"]

DRY_RUN_RESPONSES: dict[str, dict] = {
    "banking": {
        "summary_zh": "【dry-run】银行资讯测试摘要，涉及监管政策变化。",
        "score": 7.5,
        "is_key": True,
        "content_tag": "监管政策类",
        "work_impact": "【dry-run】该政策对零售贷款业务有直接影响。",
    },
    "tech": {
        "summary_zh": "【dry-run】AI工具测试摘要，项目增速迅猛。",
        "score": 8.0,
        "is_key": True,
    },
    "startup": {
        "summary_zh": "【dry-run】创业项目测试摘要。",
        "score": 7.2,
        "is_key": True,
        "ai_extra": {
            "fit_score": 7.2,
            "ai_approach": "【dry-run】可用Claude API单人开发，周期约2个月。",
            "monetization": "【dry-run】订阅制，月费99元，预计6个月回本。",
            "entry_advice": "【dry-run】建议从微信小程序切入，先验证付费意愿。",
        },
    },
}

_client = None


def _get_client():
    global _client
    if _client is None:
        from anthropic import Anthropic
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def call_claude(
    prompt: str,
    result_type: ResultType = "banking",
    model: str | None = None,
    max_tokens: int = 2000,
    dry_run: bool = False,
) -> str:
    if dry_run:
        return json.dumps(DRY_RUN_RESPONSES[result_type], ensure_ascii=False)

    default_model = (
        "claude-sonnet-4-6" if result_type == "startup"
        else "claude-haiku-4-5-20251001"
    )
    try:
        response = _get_client().messages.create(
            model=model or default_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as exc:
        logger.error("Claude API call failed: %s", exc)
        raise
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
pytest tests/test_ai.py -v
```

Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add app/ai/schemas.py app/ai/client.py tests/test_ai.py
git commit -m "feat: AI client with dry-run + Pydantic response schemas"
```

---

## Task 9: 三类 AI 处理器

**Files:**
- Create: `app/ai/banking.py`
- Create: `app/ai/tech.py`
- Create: `app/ai/startup.py`
- Create: `app/ai/processor.py`

- [ ] **Step 1: 实现 app/ai/banking.py**

```python
import logging
from app.ai.client import call_claude
from app.ai.schemas import BankingResult
from app.config import CategoryConfig
from app.fetchers.base import RawItem

logger = logging.getLogger(__name__)

BANKING_PROMPT = """\
你是一名银行零售运营专家助手。请分析以下资讯，返回 JSON（不要加代码块）：

标题：{title}
内容：{content}

返回格式（严格 JSON，不要额外文字）：
{{
  "summary_zh": "3-4句中文摘要",
  "score": <0-10浮点数，监管影响力×业务可借鉴性>,
  "is_key": <true/false>,
  "content_tag": "<监管政策类|业务方案类|竞品动态类|需求商机类|进展突破类|成果类>",
  "work_impact": "<一句话工作影响，score>=7时填充，否则填null>"
}}
"""


def process_banking_batch(
    items: list[RawItem],
    category: CategoryConfig,
    dry_run: bool = False,
) -> list[BankingResult]:
    results: list[BankingResult] = []
    threshold = category.importance_rule.is_key_threshold
    boost_tags = set(category.importance_rule.boost_tags)

    for item in items:
        content = (item.raw_text or "")[:800]
        prompt = BANKING_PROMPT.format(title=item.title, content=content)
        raw = call_claude(prompt, result_type="banking", dry_run=dry_run)
        try:
            result = BankingResult.model_validate_json(raw)
        except Exception as exc:
            logger.error("Parse failed for %r: %s", item.title, exc)
            result = BankingResult(summary_zh=item.title, score=0.0, is_key=False)

        boosted = result.content_tag in boost_tags if result.content_tag else False
        result.is_key = result.score >= threshold or (
            result.score >= threshold - 1 and boosted
        )
        if result.score < threshold:
            result.work_impact = None
        results.append(result)
    return results
```

- [ ] **Step 2: 实现 app/ai/tech.py**

```python
import logging
from app.ai.client import call_claude
from app.ai.schemas import TechResult
from app.config import CategoryConfig
from app.fetchers.base import RawItem

logger = logging.getLogger(__name__)

TECH_PROMPT = """\
你是一名关注银行运营、数据分析和AI自动化工具的技术研究员。请分析以下项目/资讯，返回 JSON（不要加代码块）：

标题：{title}
描述：{description}
热度指标（Stars/Score）：{stars}

返回格式（严格 JSON，不要额外文字）：
{{
  "summary_zh": "2-3句中文摘要",
  "score": <0-10浮点数，上升速度×与银行运营/数据分析/agent自动化的相关度>,
  "is_key": <true/false>
}}
"""


def process_tech_batch(
    items: list[RawItem],
    category: CategoryConfig,
    dry_run: bool = False,
) -> list[TechResult]:
    threshold = category.importance_rule.is_key_threshold
    results: list[TechResult] = []
    for item in items:
        stars = item.extra.get("stars") or item.extra.get("score", 0)
        prompt = TECH_PROMPT.format(
            title=item.title,
            description=(item.raw_text or "")[:400],
            stars=stars,
        )
        raw = call_claude(prompt, result_type="tech", dry_run=dry_run)
        try:
            result = TechResult.model_validate_json(raw)
        except Exception as exc:
            logger.error("Parse failed for %r: %s", item.title, exc)
            result = TechResult(summary_zh=item.title, score=0.0, is_key=False)
        result.is_key = result.score >= threshold
        results.append(result)
    return results
```

- [ ] **Step 3: 实现 app/ai/startup.py**

```python
import logging
from app.ai.client import call_claude
from app.ai.schemas import StartupResult, StartupExtra
from app.config import CategoryConfig
from app.fetchers.base import RawItem

logger = logging.getLogger(__name__)

STARTUP_PROMPT = """\
你是一名专注中国市场的AI创业顾问。请评估以下创业项目/想法，返回 JSON（不要加代码块）：

标题：{title}
描述：{description}

评分标准（四条，每条2.5分，共10分）：
1. 能用AI单人/轻团队开发
2. 启动成本低
3. 面向中国市场
4. 有清晰变现路径

返回格式（严格 JSON，不要额外文字）：
{{
  "summary_zh": "2句中文摘要",
  "score": <0-10综合适合度>,
  "is_key": <true/false>,
  "ai_extra": {{
    "fit_score": <0-10浮点数，同score>,
    "ai_approach": "能否/如何用AI单人开发的具体说明",
    "monetization": "启动成本估算与变现路径",
    "entry_advice": "给我的切入建议，1-2句"
  }}
}}
"""


def process_startup_batch(
    items: list[RawItem],
    category: CategoryConfig,
    dry_run: bool = False,
) -> list[StartupResult]:
    threshold = category.importance_rule.is_key_threshold
    results: list[StartupResult] = []
    for item in items:
        prompt = STARTUP_PROMPT.format(
            title=item.title,
            description=(item.raw_text or "")[:600],
        )
        raw = call_claude(prompt, result_type="startup", dry_run=dry_run)
        try:
            result = StartupResult.model_validate_json(raw)
        except Exception as exc:
            logger.error("Parse failed for %r: %s", item.title, exc)
            result = StartupResult(
                summary_zh=item.title, score=0.0, is_key=False,
                ai_extra=StartupExtra(fit_score=0.0, ai_approach="解析失败",
                                      monetization="解析失败", entry_advice="解析失败"),
            )
        result.is_key = result.score >= threshold
        results.append(result)
    return results
```

- [ ] **Step 4: 实现 app/ai/processor.py**

```python
from app.ai.banking import process_banking_batch
from app.ai.tech import process_tech_batch
from app.ai.startup import process_startup_batch
from app.config import CategoryConfig
from app.fetchers.base import RawItem

_DEPTH_MAP = {
    "light": process_tech_batch,
    "medium": process_tech_batch,
    "medium_deep": process_banking_batch,
    "deep": process_startup_batch,
}


def process_items(
    items: list[RawItem],
    category: CategoryConfig,
    dry_run: bool = False,
) -> list:
    processor = _DEPTH_MAP.get(category.depth_level)
    if processor is None:
        raise ValueError(f"Unknown depth_level: {category.depth_level!r}")
    return processor(items, category, dry_run=dry_run)
```

- [ ] **Step 5: 追加处理器测试到 tests/test_ai.py**

在文件末尾追加：
```python
from app.ai.processor import process_items
from app.config import CategoryConfig, ImportanceRule
from app.fetchers.base import RawItem as RI


def _banking_cat():
    return CategoryConfig(
        name="银行", slug="banking", depth_level="medium_deep",
        schedule=["morning"], enabled=True,
        importance_rule=ImportanceRule(is_key_threshold=7.0, boost_tags=["监管政策类"]),
        sources=[],
    )


def _startup_cat():
    return CategoryConfig(
        name="创业", slug="startup", depth_level="deep",
        schedule=["morning"], enabled=True,
        importance_rule=ImportanceRule(is_key_threshold=6.5),
        sources=[],
    )


def test_process_banking_dry_run():
    results = process_items([RI(title="央行降息", url="https://example.com/1",
                                raw_text="内容")], _banking_cat(), dry_run=True)
    assert len(results) == 1
    assert results[0].score > 0


def test_process_startup_dry_run():
    results = process_items([RI(title="AI记账App", url="https://example.com/2",
                                raw_text="帮用户记账")], _startup_cat(), dry_run=True)
    assert results[0].ai_extra.entry_advice


def test_unknown_depth_raises():
    bad = CategoryConfig(name="X", slug="x", depth_level="unknown",
                         schedule=["morning"], enabled=True,
                         importance_rule=ImportanceRule(is_key_threshold=7.0), sources=[])
    with pytest.raises(ValueError, match="Unknown depth_level"):
        process_items([RI(title="X", url="https://x.com")], bad, dry_run=True)
```

- [ ] **Step 6: 运行全部 AI 测试**

```bash
pytest tests/test_ai.py -v
```

Expected: all passed

- [ ] **Step 7: Commit**

```bash
git add app/ai/ tests/test_ai.py
git commit -m "feat: banking/tech/startup AI processors + depth router"
```

---

## Task 10: Feishu 推送

**Files:**
- Create: `app/push/feishu.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: 先写失败的测试**

`tests/test_pipeline.py`:
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.item import Item
from app.models.push_log import PushLog
from app.push.feishu import push_key_items


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _make_item(db, id_: int, cat: str = "banking") -> Item:
    item = Item(id=id_, source_id=1, category_slug=cat,
                title=f"Item {id_}", url=f"https://example.com/{id_}",
                dedup_hash=f"hash{id_}", summary_zh=f"摘要{id_}",
                is_key=True, score=8.0)
    db.add(item)
    db.commit()
    return item


def test_dry_run_no_push(db):
    item = _make_item(db, 1)
    result = push_key_items("morning", [item], db, dry_run=True)
    assert result is True
    assert db.query(PushLog).count() == 0


def test_push_creates_log(db):
    import respx
    import httpx as _httpx
    item = _make_item(db, 2)
    with respx.mock:
        respx.post("https://open.feishu.cn/webhook").mock(
            return_value=_httpx.Response(200, json={"code": 0}))
        result = push_key_items("morning", [item], db,
                                webhook_url="https://open.feishu.cn/webhook")
    assert result is True
    log = db.query(PushLog).first()
    assert log is not None
    assert 2 in log.item_ids


def test_no_duplicate_push(db):
    item = _make_item(db, 3)
    db.add(PushLog(slot="morning", category_slug="all", item_ids=[3]))
    db.commit()
    push_key_items("morning", [item], db, dry_run=True)
    assert db.query(PushLog).count() == 1


def test_empty_items_returns_true(db):
    assert push_key_items("morning", [], db, dry_run=True) is True
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_pipeline.py -v
```

Expected: `FAILED`

- [ ] **Step 3: 实现 app/push/feishu.py**

```python
import logging
import os
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.push_log import PushLog

logger = logging.getLogger(__name__)

_SLOT_LABELS = {"morning": "早间", "evening": "晚间"}
_CAT_LABELS = {"banking": "银行用户运营", "tech": "技术与AI工具", "startup": "个人创业"}


def _build_card(slot: str, items_by_cat: dict[str, list[Item]]) -> dict:
    date_str = datetime.now().strftime("%Y-%m-%d")
    slot_label = _SLOT_LABELS.get(slot, slot)
    elements = []
    for cat_slug, items in items_by_cat.items():
        if not items:
            continue
        elements.append({"tag": "markdown",
                          "content": f"**{_CAT_LABELS.get(cat_slug, cat_slug)}**"})
        for item in items:
            summary = (item.summary_zh or item.title)[:100]
            suffix = ""
            if item.ai_extra and "fit_score" in item.ai_extra:
                suffix = f" | 适合度 {item.ai_extra['fit_score']:.1f}"
            elements.append({"tag": "markdown",
                              "content": f"• [{item.title}]({item.url})\n  {summary}{suffix}"})
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text",
                          "content": f"📰 资讯速报 · {date_str} {slot_label}"},
                "template": "blue",
            },
            "elements": elements,
        },
    }


def push_key_items(
    slot: str,
    items: list[Item],
    db: Session,
    webhook_url: str | None = None,
    dry_run: bool = False,
) -> bool:
    if not items:
        return True

    pushed_ids: set[int] = set()
    for log in db.query(PushLog).filter_by(slot=slot).all():
        pushed_ids.update(log.item_ids)

    new_items = [i for i in items if i.id not in pushed_ids]
    if not new_items:
        logger.info("All key items already pushed for slot=%s", slot)
        return True

    items_by_cat: dict[str, list[Item]] = {}
    for item in new_items:
        items_by_cat.setdefault(item.category_slug, []).append(item)

    if dry_run:
        logger.info("[dry-run] Would push %d items to Feishu", len(new_items))
        return True

    url = webhook_url or os.environ.get("FEISHU_WEBHOOK_URL")
    if not url:
        raise ValueError("FEISHU_WEBHOOK_URL not set")

    try:
        resp = httpx.post(url, json=_build_card(slot, items_by_cat), timeout=10)
        resp.raise_for_status()
        if resp.json().get("code") != 0:
            logger.error("Feishu error: %s", resp.json())
            return False
    except Exception as exc:
        logger.error("Feishu push failed: %s", exc)
        return False

    db.add(PushLog(slot=slot, category_slug="all",
                   item_ids=[i.id for i in new_items]))
    db.commit()
    logger.info("Pushed %d key items to Feishu for slot=%s", len(new_items), slot)
    return True
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_pipeline.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/push/feishu.py tests/test_pipeline.py
git commit -m "feat: Feishu push with push_log dedup"
```

---

## Task 11: Pipeline 主流程

**Files:**
- Create: `app/scheduler/pipeline.py`
- Test: `tests/test_pipeline.py`（追加）

- [ ] **Step 1: 实现 app/scheduler/pipeline.py**

```python
import asyncio
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import AppConfig, CategoryConfig
from app.fetchers.base import RawItem
from app.fetchers.registry import get_fetcher
from app.ai.processor import process_items
from app.models.item import Item
from app.models.run_log import RunLog
from app.push.feishu import push_key_items
from app.scheduler.dedup import filter_new_items

logger = logging.getLogger(__name__)


async def _fetch_category(category: CategoryConfig) -> list[RawItem]:
    enabled = [s for s in category.sources if s.enabled]
    results = await asyncio.gather(
        *[get_fetcher(src).fetch() for src in enabled],
        return_exceptions=True,
    )
    items: list[RawItem] = []
    for src, result in zip(enabled, results):
        if isinstance(result, Exception):
            logger.error("Source %r fetch error: %s", src.name, result)
        else:
            items.extend(result)
    return items


def _save_items(
    raw_items: list[RawItem],
    ai_results: list,
    category: CategoryConfig,
    db: Session,
) -> list[Item]:
    saved: list[Item] = []
    for raw, ai in zip(raw_items, ai_results):
        ai_extra = None
        if hasattr(ai, "ai_extra") and ai.ai_extra:
            ai_extra = ai.ai_extra.model_dump()
        if hasattr(ai, "work_impact") and ai.work_impact:
            ai_extra = ai_extra or {}
            ai_extra["work_impact"] = ai.work_impact

        item = Item(
            source_id=0,
            category_slug=category.slug,
            title=raw.title,
            url=raw.url,
            raw_text=(raw.raw_text[:2000] if raw.raw_text else None),
            summary_zh=getattr(ai, "summary_zh", None),
            score=getattr(ai, "score", None),
            is_key=getattr(ai, "is_key", False),
            content_tag=getattr(ai, "content_tag", None),
            ai_extra=ai_extra,
            published_at=raw.published_at,
            dedup_hash=raw.extra["dedup_hash"],
        )
        db.add(item)
        try:
            db.flush()
            saved.append(item)
        except Exception as exc:
            db.rollback()
            logger.warning("Skip duplicate item %r: %s", raw.url, exc)
    db.commit()
    return saved


def run_pipeline(
    slot: str,
    categories: list[CategoryConfig],
    db: Session,
    config: AppConfig,
    dry_run: bool = False,
) -> dict:
    summary: dict = {"total_fetched": 0, "total_new": 0, "categories": {}}
    all_key_items: list[Item] = []

    for category in categories:
        if slot not in category.schedule or not category.enabled:
            continue

        run_log = RunLog(slot=slot, category_slug=category.slug,
                         started_at=datetime.utcnow(), status="running",
                         items_fetched=0, items_new=0)
        db.add(run_log)
        db.commit()

        try:
            raw_items = asyncio.run(_fetch_category(category))
            new_items = filter_new_items(raw_items, db, config.settings.dedup_days)
            ai_results = process_items(new_items, category, dry_run=dry_run)
            saved = _save_items(new_items, ai_results, category, db)

            key_items = [i for i in saved if i.is_key]
            all_key_items.extend(key_items)

            run_log.status = "success"
            run_log.items_fetched = len(raw_items)
            run_log.items_new = len(saved)
            run_log.finished_at = datetime.utcnow()
            db.commit()

            cat_summary = {"fetched": len(raw_items), "new": len(saved),
                           "key": len(key_items)}
            summary["categories"][category.slug] = cat_summary
            summary["total_fetched"] += len(raw_items)
            summary["total_new"] += len(saved)

        except Exception as exc:
            logger.error("Pipeline error for %s: %s", category.slug, exc)
            run_log.status = "failed"
            run_log.error_msg = str(exc)
            run_log.finished_at = datetime.utcnow()
            db.commit()
            summary["categories"][category.slug] = {"error": str(exc)}

    push_key_items(slot, all_key_items, db, dry_run=dry_run)
    return summary
```

- [ ] **Step 2: 追加 pipeline 集成测试到 tests/test_pipeline.py**

在文件末尾追加：
```python
from unittest.mock import patch, AsyncMock
from app.scheduler.pipeline import run_pipeline
from app.config import AppConfig, CategoryConfig, ImportanceRule, SourceConfig, Settings


def _make_config() -> AppConfig:
    cat = CategoryConfig(
        name="银行", slug="banking", depth_level="medium_deep",
        schedule=["morning"], enabled=True,
        importance_rule=ImportanceRule(is_key_threshold=7.0, boost_tags=[]),
        sources=[SourceConfig(name="RSS", fetch_type="rss",
                              feed_url="https://example.com/feed",
                              enabled=True, extra={})],
    )
    return AppConfig(settings=Settings(), categories=[cat])


@pytest.fixture
def full_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_pipeline_dry_run_runs(full_db):
    from app.fetchers.base import RawItem
    mock_items = [RawItem(title="央行降息", url="https://example.com/news1",
                          raw_text="内容")]
    cfg = _make_config()
    # asyncio.run 可以直接执行 AsyncMock 返回的协程，无需额外 patch
    with patch("app.scheduler.pipeline._fetch_category",
               new_callable=AsyncMock, return_value=mock_items):
        summary = run_pipeline("morning", cfg.categories, full_db, cfg, dry_run=True)
    assert "banking" in summary["categories"]


def test_pipeline_skips_wrong_slot(full_db):
    cfg = _make_config()
    with patch("app.scheduler.pipeline._fetch_category",
               new_callable=AsyncMock, return_value=[]):
        summary = run_pipeline("evening", cfg.categories, full_db, cfg, dry_run=True)
    assert summary["total_fetched"] == 0
```

- [ ] **Step 3: 运行 pipeline 测试**

```bash
pytest tests/test_pipeline.py -v
```

Expected: all passed

- [ ] **Step 4: Commit**

```bash
git add app/scheduler/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline orchestrator (fetch→dedup→AI→save→push)"
```

---

## Task 12: CLI 入口 + FastAPI 基础 + 最终验收

**Files:**
- Create: `app/run.py`
- Create: `app/main.py`
- Create: `crontab.example`
- Create: `tests/conftest.py`

- [ ] **Step 1: 实现 app/run.py**

```python
"""
CLI entry point.

Usage:
  python -m app.run --slot morning
  python -m app.run --slot morning --category banking
  python -m app.run --slot morning --dry-run
"""
import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="News platform pipeline")
    parser.add_argument("--slot", required=True, choices=["morning", "evening"])
    parser.add_argument("--category", default="all",
                        help="Category slug or 'all'")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip real API calls")
    args = parser.parse_args()

    from app.config import get_config
    from app.models.base import init_db, SessionLocal
    from app.scheduler.pipeline import run_pipeline

    Path("data").mkdir(exist_ok=True)
    init_db()

    cfg = get_config()
    categories = cfg.categories
    if args.category != "all":
        categories = [c for c in categories if c.slug == args.category]
        if not categories:
            logger.error("Category %r not found", args.category)
            sys.exit(1)

    db = SessionLocal()
    try:
        summary = run_pipeline(args.slot, categories, db, cfg,
                               dry_run=args.dry_run)
        logger.info("Done: %s", summary)
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 实现 app/main.py**

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="News Platform", version="0.1.0")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
```

- [ ] **Step 3: 创建 tests/conftest.py**

```python
import asyncio
import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("RSSHUB_BASE_URL", "http://localhost:1200")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

- [ ] **Step 4: 创建 crontab.example**

```
# 个人资讯平台定时任务
# 安装方法: crontab -e 然后粘贴以下行（修改路径和 python 路径）

# 早间 9:00 — 全部类别（银行/技术/创业）
0 9 * * * cd /opt/news-platform && /opt/news-platform/.venv/bin/python -m app.run --slot morning --category all >> /var/log/news-platform/morning.log 2>&1

# 晚间 19:00 — 仅银行类别
0 19 * * * cd /opt/news-platform && /opt/news-platform/.venv/bin/python -m app.run --slot evening --category banking >> /var/log/news-platform/evening.log 2>&1
```

- [ ] **Step 5: 运行全部测试**

```bash
pytest tests/ -v --tb=short
```

Expected: all passed

- [ ] **Step 6: 验证 CLI dry-run 可执行**

```bash
RSSHUB_BASE_URL=http://localhost:1200 \
ANTHROPIC_API_KEY=dummy \
python -m app.run --slot morning --category banking --dry-run 2>&1 | tail -3
```

Expected 最后一行包含: `Done:`（有 RSS fetch 失败日志是正常的，流程不中断）

- [ ] **Step 7: 验证 FastAPI health 端点**

```bash
uvicorn app.main:app --port 8001 &
sleep 2
curl http://localhost:8001/health
kill %1
```

Expected: `{"status":"ok"}`

- [ ] **Step 8: 最终 commit**

```bash
git add app/run.py app/main.py tests/conftest.py crontab.example
git commit -m "feat: CLI entry point + FastAPI health + crontab.example"
```

---

## 验收标准

全部完成后，以下命令均成功：

```bash
# 全部测试通过
pytest tests/ -v

# dry-run 端到端跑通
RSSHUB_BASE_URL=http://localhost:1200 ANTHROPIC_API_KEY=dummy \
python -m app.run --slot morning --category banking --dry-run

# FastAPI 健康检查
uvicorn app.main:app --port 8000 &
curl http://localhost:8000/health  # → {"status":"ok"}
```

**Plan 2（Web 前端 — 首页/分类/搜索/归档/晨晚报/管理页）** 和 **Plan 3（Docker + Nginx + 部署）** 在本 Plan 验收后编写。
