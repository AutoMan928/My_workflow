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
