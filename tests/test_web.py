import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SITE_PASSWORD", "testpassword")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
os.environ.setdefault("RSSHUB_BASE_URL", "http://localhost:1200")

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.models.base import Base, get_db
from app.models.item import Item
from app.models.push_log import PushLog

# ── 共享测试数据库 ─────────────────────────────────────────────────────────────
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
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

# 对测试引擎初始化 FTS5
from sqlalchemy import text as _t
with _engine.connect() as _c:
    _c.execute(_t("CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(title, summary_zh, content='items', content_rowid='id')"))
    _c.execute(_t("INSERT OR IGNORE INTO items_fts(rowid, title, summary_zh) SELECT id, title, COALESCE(summary_zh,'') FROM items"))
    _c.commit()


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
    assert resp.headers["location"] in ("/", "http://testserver/")


def test_logout(authed):
    resp = authed.get("/logout", follow_redirects=False)
    assert resp.status_code == 302


# ── Task 2: Home 测试 ──────────────────────────────────────────────────────────
def test_home_200(authed):
    resp = authed.get("/")
    assert resp.status_code == 200


def test_home_shows_three_sections(authed):
    resp = authed.get("/")
    assert "银行用户运营" in resp.text
    assert "技术与AI工具" in resp.text
    assert "个人创业" in resp.text


def test_home_shows_seeded_items(authed):
    resp = authed.get("/")
    assert "银行降息公告" in resp.text
    assert "GPT-5 发布" in resp.text


def test_home_key_badge(authed):
    resp = authed.get("/")
    assert "重点" in resp.text


# ── Task 3: Category 测试 ──────────────────────────────────────────────────────
def test_category_200(authed):
    resp = authed.get("/category/banking")
    assert resp.status_code == 200
    assert "银行用户运营" in resp.text


def test_category_shows_items(authed):
    resp = authed.get("/category/banking")
    assert "银行降息公告" in resp.text


def test_category_unknown_slug_404(authed):
    resp = authed.get("/category/unknown")
    assert resp.status_code == 404


def test_category_htmx_returns_partial(authed):
    resp = authed.get("/category/banking?page=0",
                      headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert "<html" not in resp.text
    assert "银行降息公告" in resp.text


# ── Task 4: Item detail 测试 ───────────────────────────────────────────────────
def test_item_detail_200(authed):
    db = _Session()
    item = db.query(Item).first()
    item_id = item.id
    db.close()
    resp = authed.get(f"/item/{item_id}")
    assert resp.status_code == 200


def test_item_detail_shows_title(authed):
    db = _Session()
    item = db.query(Item).first()
    item_id, title = item.id, item.title
    db.close()
    resp = authed.get(f"/item/{item_id}")
    assert title in resp.text


def test_item_detail_shows_summary(authed):
    db = _Session()
    item = db.query(Item).filter(Item.summary_zh.isnot(None)).first()
    item_id, summary = item.id, item.summary_zh
    db.close()
    resp = authed.get(f"/item/{item_id}")
    assert summary in resp.text


def test_item_toggle_read(authed):
    db = _Session()
    item = db.query(Item).first()
    item_id, original = item.id, item.is_read
    db.close()
    authed.post(f"/item/{item_id}/toggle", data={"field": "is_read"})
    db = _Session()
    updated = db.query(Item).filter_by(id=item_id).first()
    assert updated.is_read != original
    db.close()


def test_item_not_found(authed):
    resp = authed.get("/item/99999")
    assert resp.status_code == 404


# ── Task 5: Search 测试 ────────────────────────────────────────────────────────
def test_search_page_200(authed):
    resp = authed.get("/search")
    assert resp.status_code == 200


def test_search_returns_results(authed):
    resp = authed.get("/search?q=银行")
    assert resp.status_code == 200
    assert "银行降息公告" in resp.text


def test_search_no_results(authed):
    resp = authed.get("/search?q=xyzabc123notfound")
    assert resp.status_code == 200
    assert "没有找到" in resp.text


def test_search_unauthenticated_redirects():
    from starlette.testclient import TestClient
    with TestClient(app) as client:
        resp = client.get("/search", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


# ── Task 6: Archive + Report 测试 ─────────────────────────────────────────────
def test_archive_200(authed):
    resp = authed.get("/archive")
    assert resp.status_code == 200


def test_archive_shows_today(authed):
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    resp = authed.get("/archive")
    assert today in resp.text


def test_report_200(authed):
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    resp = authed.get(f"/report/morning/{today}")
    assert resp.status_code == 200


def test_report_shows_pushed_items(authed):
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    resp = authed.get(f"/report/morning/{today}")
    assert "银行降息公告" in resp.text


def test_report_invalid_slot_404(authed):
    resp = authed.get("/report/weekly/2026-01-01")
    assert resp.status_code == 404


# ── Task 7: Admin sources 测试 ────────────────────────────────────────────────
def test_admin_sources_200(authed):
    resp = authed.get("/admin/sources")
    assert resp.status_code == 200
    assert "来源管理" in resp.text


def test_admin_sources_lists_sources(authed):
    resp = authed.get("/admin/sources")
    assert any(t in resp.text for t in ("rss", "api_github", "api_hn", "api_ph", "api_hf", "scraper"))
