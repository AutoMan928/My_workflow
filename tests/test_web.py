import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SITE_PASSWORD", "testpassword")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("RSSHUB_BASE_URL", "http://localhost:1200")

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from app.models.base import Base, get_db
from app.models.item import Item
from app.models.push_log import PushLog

# ── 共享测试数据库 ─────────────────────────────────────────────────────────────
_engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine)


def _override_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


from app.main import app  # noqa: E402
from app.web.deps import make_session_cookie, COOKIE_NAME  # noqa: E402

app.dependency_overrides[get_db] = _override_db


# ── 种子数据 ──────────────────────────────────────────────────────────────────
def _seed():
    db = _Session()
    items = [
        Item(source_id=1, category_slug="banking", title="银行降息公告",
             url="https://example.com/banking/1", dedup_hash="h1",
             summary_zh="央行公告摘要", score=8.5, is_key=True,
             fetched_at=datetime.utcnow()),
        Item(source_id=1, category_slug="tech", title="GPT-5 发布",
             url="https://example.com/tech/1", dedup_hash="h2",
             summary_zh="AI工具更新摘要", score=9.0, is_key=True,
             fetched_at=datetime.utcnow()),
        Item(source_id=1, category_slug="startup", title="AI记账App获融资",
             url="https://example.com/startup/1", dedup_hash="h3",
             summary_zh="创业项目摘要", score=7.0, is_key=False,
             fetched_at=datetime.utcnow()),
    ]
    db.add_all(items)
    db.flush()
    db.add(PushLog(slot="morning", category_slug="all",
                   item_ids=[items[0].id, items[1].id]))
    db.commit()
    db.close()


_seed()


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def anon():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def authed():
    with TestClient(app) as c:
        c.cookies.set(COOKIE_NAME, make_session_cookie())
        yield c


# ── Task 1: Auth 测试 ──────────────────────────────────────────────────────────
def test_login_page(anon):
    resp = anon.get("/login")
    assert resp.status_code == 200
    assert "登录" in resp.text


def test_login_wrong_password(anon):
    resp = anon.post("/login", data={"password": "wrong"}, follow_redirects=False)
    assert resp.status_code == 401
    assert "密码错误" in resp.text


def test_unauthenticated_redirects(anon):
    resp = anon.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_login_correct_password(anon):
    resp = anon.post("/login", data={"password": "testpassword"}, follow_redirects=False)
    assert resp.status_code == 302
    assert COOKIE_NAME in resp.cookies


def test_logout(authed):
    resp = authed.get("/logout", follow_redirects=False)
    assert resp.status_code == 302
