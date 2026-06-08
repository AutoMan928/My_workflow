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
