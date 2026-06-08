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
    from unittest.mock import patch, MagicMock
    item = _make_item(db, 2)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 0}
    with patch("httpx.post", return_value=mock_resp):
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
