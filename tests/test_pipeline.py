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
