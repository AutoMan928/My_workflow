# Web 前端实现计划（Plan 2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为个人资讯平台构建完整 Web 前端——含密码登录、首页三分区、分类列表（HTMX 分页）、条目详情、FTS5 全文搜索、归档、晨晚报回看、来源管理。

**Architecture:** FastAPI + Jinja2 服务端渲染；Tailwind CSS CDN + HTMX CDN（无构建步骤）；itsdangerous 签名 cookie 单用户认证（48 h 有效）；SQLite FTS5 支持全文搜索；HTMX 处理分类分页和已读/收藏开关的局部更新。

**Tech Stack:** FastAPI, Jinja2, Tailwind CSS (CDN), HTMX (CDN), itsdangerous, SQLite FTS5, pytest + starlette.testclient

---

## 文件清单

```
app/
├── main.py                          # 修改：逐步挂载所有 web 路由
├── web/
│   ├── __init__.py                  # 空
│   ├── deps.py                      # templates, check_auth(), make_session_cookie(), COOKIE_NAME
│   └── routes/
│       ├── __init__.py              # 空
│       ├── auth.py                  # GET/POST /login, GET /logout
│       ├── home.py                  # GET /
│       ├── category.py              # GET /category/{slug}（含 HTMX 分页）
│       ├── item.py                  # GET /item/{id}, POST /item/{id}/toggle
│       ├── search.py                # GET /search（FTS5）
│       ├── archive.py               # GET /archive, GET /report/{slot}/{date}
│       └── admin.py                 # GET /admin/sources, POST /admin/sources/toggle, POST /admin/sources/url
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── home.html
│       ├── category.html
│       ├── _items_partial.html      # HTMX 分页局部模板
│       ├── item.html
│       ├── search.html
│       ├── archive.html
│       ├── report.html
│       └── admin_sources.html
└── models/
    └── base.py                      # 修改：init_db() 追加 _init_fts()
tests/
└── test_web.py                      # 贯穿 Task 1-8 的全量 Web 路由测试
```

---

## Python 版本约定（强制）

- Python 3.11+：`X | None`、`list[X]`，**禁止** `Optional[X]`、`List[X]`
- **禁止** `from __future__ import annotations`
- **禁止** 函数/方法 docstring（模块级 usage string 除外）
- `httpx.AsyncClient(timeout=15, trust_env=False)` — `trust_env=False` 强制
- Pydantic 更新用 `model_copy(update={...})`，禁止直接修改对象

---

## Task 1: 认证模块 + 测试基础设施

**Files:**
- Create: `app/web/__init__.py`
- Create: `app/web/routes/__init__.py`
- Create: `app/web/deps.py`
- Create: `app/web/routes/auth.py`
- Create: `app/web/templates/base.html`
- Create: `app/web/templates/login.html`
- Modify: `app/main.py`
- Create: `tests/test_web.py`

- [ ] **Step 1: 创建 tests/test_web.py（TestClient 基础设施 + 认证测试）**

```python
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


def test_login_correct_password(anon):
    resp = anon.post("/login", data={"password": "testpassword"}, follow_redirects=False)
    assert resp.status_code == 302
    assert COOKIE_NAME in resp.cookies


def test_unauthenticated_redirects(anon):
    resp = anon.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_logout(authed):
    resp = authed.get("/logout", follow_redirects=False)
    assert resp.status_code == 302
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v 2>&1 | head -20
```

Expected: `FAILED` 或 `ImportError`（app.web 不存在）

- [ ] **Step 3: 创建空 __init__ 文件和模板目录**

```bash
mkdir -p app/web/routes app/web/templates
touch app/web/__init__.py app/web/routes/__init__.py
```

- [ ] **Step 4: 创建 app/web/deps.py**

```python
import os
from fastapi import Request
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

COOKIE_NAME = "news_session"
_COOKIE_MAX_AGE = 48 * 3600
_SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
_signer = URLSafeTimedSerializer(_SECRET_KEY)

templates = Jinja2Templates(directory="app/web/templates")


def make_session_cookie() -> str:
    return _signer.dumps("authenticated")


def check_auth(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        _signer.loads(token, max_age=_COOKIE_MAX_AGE)
        return True
    except (SignatureExpired, BadSignature):
        return False
```

- [ ] **Step 5: 创建 app/web/routes/auth.py**

```python
import os
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.deps import COOKIE_NAME, check_auth, make_session_cookie, templates

router = APIRouter()
_SITE_PASSWORD = os.environ.get("SITE_PASSWORD", "changeme")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if check_auth(request):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
async def login_submit(request: Request, password: str = Form(...)):
    if password != _SITE_PASSWORD:
        return templates.TemplateResponse(
            request, "login.html", {"error": "密码错误"}, status_code=401
        )
    resp = RedirectResponse(url="/", status_code=302)
    resp.set_cookie(COOKIE_NAME, make_session_cookie(),
                    max_age=48 * 3600, httponly=True, samesite="lax")
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(COOKIE_NAME)
    return resp
```

- [ ] **Step 6: 创建 app/web/templates/base.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}资讯平台{% endblock %}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/htmx.org@1.9.10"></script>
</head>
<body class="bg-gray-50 min-h-screen">
  <nav class="bg-white border-b px-6 py-3 flex items-center gap-4 text-sm sticky top-0 z-10 shadow-sm">
    <a href="/" class="font-bold text-base">📰 资讯</a>
    <a href="/category/banking" class="text-gray-600 hover:text-gray-900">银行运营</a>
    <a href="/category/tech" class="text-gray-600 hover:text-gray-900">技术AI</a>
    <a href="/category/startup" class="text-gray-600 hover:text-gray-900">创业</a>
    <a href="/search" class="text-gray-600 hover:text-gray-900">🔍 搜索</a>
    <a href="/archive" class="text-gray-600 hover:text-gray-900">📅 归档</a>
    <div class="ml-auto flex gap-4">
      <a href="/admin/sources" class="text-gray-400 hover:text-gray-600">⚙️</a>
      <a href="/logout" class="text-gray-400 hover:text-gray-600">退出</a>
    </div>
  </nav>
  <main class="max-w-4xl mx-auto px-4 py-6">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 7: 创建 app/web/templates/login.html**

```html
{% extends "base.html" %}
{% block title %}登录{% endblock %}
{% block content %}
<div class="max-w-sm mx-auto mt-20">
  <h1 class="text-2xl font-bold text-center mb-8">📰 资讯平台</h1>
  <form method="post" action="/login" class="bg-white rounded-xl shadow p-8 flex flex-col gap-4">
    {% if error %}<p class="text-red-500 text-sm text-center">{{ error }}</p>{% endif %}
    <input type="password" name="password" placeholder="密码"
           class="border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
           autofocus required />
    <button type="submit"
            class="bg-blue-600 text-white rounded-lg py-2 hover:bg-blue-700 transition">
      登录
    </button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 8: 修改 app/main.py，挂载 auth 路由**

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.web.routes import auth

app = FastAPI(title="News Platform", version="0.1.0")
app.include_router(auth.router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
```

- [ ] **Step 9: 运行 Task 1 测试，确认通过**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v -k "login or logout or unauthenticated"
```

Expected: 5 passed

- [ ] **Step 10: Commit**

```bash
cd /Users/daichao/news-platform && git add app/web/ app/main.py tests/test_web.py && git commit -m "feat: auth routes (login/logout) + base/login templates"
```

---

## Task 2: 首页

**Files:**
- Create: `app/web/routes/home.py`
- Create: `app/web/templates/home.html`
- Modify: `app/main.py`
- Modify: `tests/test_web.py`（追加）

- [ ] **Step 1: 追加测试到 tests/test_web.py**

在文件末尾追加：

```python
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
```

- [ ] **Step 2: 运行，确认失败**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v -k "test_home" 2>&1 | head -15
```

Expected: FAILED（404 或 ImportError）

- [ ] **Step 3: 创建 app/web/routes/home.py**

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.item import Item
from app.web.deps import check_auth, templates

router = APIRouter()

_CATEGORY_LABELS = {
    "banking": "银行用户运营",
    "tech": "技术与AI工具",
    "startup": "个人创业",
}
_CATEGORY_ORDER = ["banking", "tech", "startup"]
_HOME_LIMIT = 10


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)

    sections = []
    for slug in _CATEGORY_ORDER:
        items = (
            db.query(Item)
            .filter(Item.category_slug == slug)
            .order_by(desc(Item.fetched_at))
            .limit(_HOME_LIMIT)
            .all()
        )
        sections.append({
            "slug": slug,
            "label": _CATEGORY_LABELS[slug],
            "items": items,
        })

    return templates.TemplateResponse(request, "home.html", {"sections": sections})
```

- [ ] **Step 4: 创建 app/web/templates/home.html**

```html
{% extends "base.html" %}
{% block title %}首页 · 资讯平台{% endblock %}
{% block content %}
{% for section in sections %}
<section class="mb-10">
  <div class="flex items-center gap-3 mb-4">
    <h2 class="text-lg font-bold">{{ section.label }}</h2>
    <a href="/category/{{ section.slug }}"
       class="text-sm text-blue-500 hover:underline">全部 →</a>
  </div>
  {% if not section.items %}
    <p class="text-gray-400 text-sm">暂无内容</p>
  {% else %}
  <div class="flex flex-col gap-2">
    {% for item in section.items %}
    <a href="/item/{{ item.id }}"
       class="bg-white rounded-lg border px-4 py-3 hover:shadow-sm transition flex items-start gap-3
              {{ 'opacity-60' if item.is_read else '' }}">
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
          {% if item.is_key %}
          <span class="text-xs bg-red-500 text-white rounded px-1.5 py-0.5 shrink-0">重点</span>
          {% endif %}
          <span class="font-medium text-gray-900 truncate">{{ item.title }}</span>
        </div>
        {% if item.summary_zh %}
        <p class="text-sm text-gray-500 mt-1 line-clamp-1">{{ item.summary_zh }}</p>
        {% endif %}
      </div>
      {% if item.score %}
      <span class="text-xs text-gray-400 shrink-0">{{ "%.1f"|format(item.score) }}</span>
      {% endif %}
    </a>
    {% endfor %}
  </div>
  {% endif %}
</section>
{% endfor %}
{% endblock %}
```

- [ ] **Step 5: 在 main.py 中追加 home router**

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.web.routes import auth, home

app = FastAPI(title="News Platform", version="0.1.0")
app.include_router(auth.router)
app.include_router(home.router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
```

- [ ] **Step 6: 运行测试**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v -k "test_home"
```

Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
cd /Users/daichao/news-platform && git add app/web/routes/home.py app/web/templates/home.html app/main.py tests/test_web.py && git commit -m "feat: home page with three-category sections"
```

---

## Task 3: 分类页（含 HTMX 分页）

**Files:**
- Create: `app/web/routes/category.py`
- Create: `app/web/templates/category.html`
- Create: `app/web/templates/_items_partial.html`
- Modify: `app/main.py`
- Modify: `tests/test_web.py`（追加）

- [ ] **Step 1: 追加测试**

```python
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
```

- [ ] **Step 2: 运行，确认失败**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v -k "test_category" 2>&1 | head -15
```

- [ ] **Step 3: 创建 app/web/routes/category.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.item import Item
from app.web.deps import check_auth, templates

router = APIRouter()

_PAGE_SIZE = 20
_CATEGORY_LABELS = {
    "banking": "银行用户运营",
    "tech": "技术与AI工具",
    "startup": "个人创业",
}


@router.get("/category/{slug}", response_class=HTMLResponse)
async def category_page(
    slug: str,
    request: Request,
    page: int = 0,
    only_key: bool = False,
    db: Session = Depends(get_db),
):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    if slug not in _CATEGORY_LABELS:
        raise HTTPException(status_code=404, detail="类别不存在")

    query = db.query(Item).filter(Item.category_slug == slug)
    if only_key:
        query = query.filter(Item.is_key.is_(True))
    rows = query.order_by(desc(Item.fetched_at)).offset(page * _PAGE_SIZE).limit(_PAGE_SIZE + 1).all()

    has_more = len(rows) > _PAGE_SIZE
    items = rows[:_PAGE_SIZE]

    ctx = {
        "slug": slug,
        "label": _CATEGORY_LABELS[slug],
        "items": items,
        "page": page,
        "next_page": page + 1,
        "has_more": has_more,
        "only_key": only_key,
    }

    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(request, "_items_partial.html", ctx)
    return templates.TemplateResponse(request, "category.html", ctx)
```

- [ ] **Step 4: 创建 app/web/templates/_items_partial.html**

```html
{% for item in items %}
<a href="/item/{{ item.id }}"
   class="bg-white rounded-lg border px-4 py-3 hover:shadow-sm transition flex items-start gap-3
          {{ 'opacity-60' if item.is_read else '' }}">
  <div class="flex-1 min-w-0">
    <div class="flex items-center gap-2">
      {% if item.is_key %}
      <span class="text-xs bg-red-500 text-white rounded px-1.5 py-0.5 shrink-0">重点</span>
      {% endif %}
      {% if item.content_tag %}
      <span class="text-xs bg-gray-100 text-gray-500 rounded px-1.5 py-0.5 shrink-0">{{ item.content_tag }}</span>
      {% endif %}
      <span class="font-medium text-gray-900 truncate">{{ item.title }}</span>
    </div>
    {% if item.summary_zh %}
    <p class="text-sm text-gray-500 mt-1 line-clamp-2">{{ item.summary_zh }}</p>
    {% endif %}
    <p class="text-xs text-gray-400 mt-1">{{ item.fetched_at.strftime("%m-%d %H:%M") if item.fetched_at else "" }}</p>
  </div>
  {% if item.score %}
  <span class="text-sm font-medium text-blue-500 shrink-0">{{ "%.1f"|format(item.score) }}</span>
  {% endif %}
</a>
{% endfor %}

{% if has_more %}
<div id="load-more-trigger"
     hx-get="/category/{{ slug }}?page={{ next_page }}{% if only_key %}&only_key=true{% endif %}"
     hx-trigger="revealed"
     hx-target="#load-more-trigger"
     hx-swap="outerHTML"
     hx-headers='{"HX-Request": "true"}'
     class="py-4 text-center text-gray-400 text-sm">
  加载更多...
</div>
{% endif %}
```

- [ ] **Step 5: 创建 app/web/templates/category.html**

```html
{% extends "base.html" %}
{% block title %}{{ label }} · 资讯平台{% endblock %}
{% block content %}
<div class="flex items-center gap-4 mb-6">
  <h1 class="text-xl font-bold">{{ label }}</h1>
  <label class="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer">
    <input type="checkbox" {% if only_key %}checked{% endif %}
           onchange="location.href='/category/{{ slug }}?only_key='+this.checked"
           class="rounded" />
    仅重点
  </label>
</div>
<div id="item-list" class="flex flex-col gap-2">
  {% include "_items_partial.html" %}
</div>
{% endblock %}
```

- [ ] **Step 6: 在 main.py 中追加 category router**

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.web.routes import auth, home, category

app = FastAPI(title="News Platform", version="0.1.0")
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(category.router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
```

- [ ] **Step 7: 运行测试**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v -k "test_category"
```

Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
cd /Users/daichao/news-platform && git add app/web/routes/category.py app/web/templates/category.html app/web/templates/_items_partial.html app/main.py tests/test_web.py && git commit -m "feat: category page with HTMX infinite scroll pagination"
```

---

## Task 4: 条目详情 + 已读/收藏开关

**Files:**
- Create: `app/web/routes/item.py`
- Create: `app/web/templates/item.html`
- Modify: `app/main.py`
- Modify: `tests/test_web.py`（追加）

- [ ] **Step 1: 追加测试**

```python
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
```

- [ ] **Step 2: 运行，确认失败**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v -k "test_item" 2>&1 | head -15
```

- [ ] **Step 3: 创建 app/web/routes/item.py**

```python
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.item import Item
from app.web.deps import check_auth, templates

router = APIRouter()

_TOGGLEABLE = {"is_read", "is_saved"}


@router.get("/item/{item_id}", response_class=HTMLResponse)
async def item_detail(item_id: int, request: Request, db: Session = Depends(get_db)):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    item = db.query(Item).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="条目不存在")
    return templates.TemplateResponse(request, "item.html", {"item": item})


@router.post("/item/{item_id}/toggle", response_class=HTMLResponse)
async def toggle_field(
    item_id: int,
    request: Request,
    field: str = Form(...),
    db: Session = Depends(get_db),
):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    if field not in _TOGGLEABLE:
        raise HTTPException(status_code=400, detail="Invalid field")
    item = db.query(Item).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404)
    setattr(item, field, not getattr(item, field))
    db.commit()
    db.refresh(item)
    is_on = getattr(item, field)
    if field == "is_read":
        btn_text = "已读" if is_on else "标为已读"
    else:
        btn_text = "已收藏" if is_on else "收藏"
    btn_class = "bg-gray-700 text-white" if is_on else "bg-white text-gray-700 border"
    return HTMLResponse(
        f'<button hx-post="/item/{item_id}/toggle" hx-vals=\'{{"field":"{field}"}}\' '
        f'hx-target="this" hx-swap="outerHTML" '
        f'class="rounded px-3 py-1 text-sm {btn_class}">{btn_text}</button>'
    )
```

- [ ] **Step 4: 创建 app/web/templates/item.html**

```html
{% extends "base.html" %}
{% block title %}{{ item.title }} · 资讯平台{% endblock %}
{% block content %}
<div class="bg-white rounded-xl border p-6 max-w-2xl">
  <div class="flex items-start gap-3 mb-4 flex-wrap">
    {% if item.is_key %}<span class="text-xs bg-red-500 text-white rounded px-1.5 py-0.5 mt-0.5">重点</span>{% endif %}
    {% if item.content_tag %}<span class="text-xs bg-gray-100 text-gray-500 rounded px-1.5 py-0.5 mt-0.5">{{ item.content_tag }}</span>{% endif %}
    <h1 class="text-xl font-bold leading-tight w-full">{{ item.title }}</h1>
  </div>

  <div class="flex gap-2 mb-6 flex-wrap">
    <button hx-post="/item/{{ item.id }}/toggle" hx-vals='{"field":"is_read"}'
            hx-target="this" hx-swap="outerHTML"
            class="rounded px-3 py-1 text-sm {{ 'bg-gray-700 text-white' if item.is_read else 'bg-white text-gray-700 border' }}">
      {{ "已读" if item.is_read else "标为已读" }}
    </button>
    <button hx-post="/item/{{ item.id }}/toggle" hx-vals='{"field":"is_saved"}'
            hx-target="this" hx-swap="outerHTML"
            class="rounded px-3 py-1 text-sm {{ 'bg-gray-700 text-white' if item.is_saved else 'bg-white text-gray-700 border' }}">
      {{ "已收藏" if item.is_saved else "收藏" }}
    </button>
    <a href="{{ item.url }}" target="_blank" rel="noopener"
       class="ml-auto rounded px-3 py-1 text-sm bg-blue-600 text-white hover:bg-blue-700">
      原文 ↗
    </a>
  </div>

  {% if item.summary_zh %}
  <div class="mb-6">
    <h2 class="text-sm font-semibold text-gray-500 mb-2">AI 摘要</h2>
    <p class="text-gray-800 leading-relaxed">{{ item.summary_zh }}</p>
  </div>
  {% endif %}

  {% if item.score %}
  <p class="text-sm text-gray-500 mb-4">评分：<span class="font-medium text-blue-600">{{ "%.1f"|format(item.score) }}</span></p>
  {% endif %}

  {% if item.ai_extra %}
  <div class="mt-4 border-t pt-4 flex flex-col gap-3">
    <h2 class="text-sm font-semibold text-gray-500">AI 分析</h2>
    {% if item.ai_extra.get("work_impact") %}
    <div><span class="text-xs text-gray-400">工作影响</span><p class="text-gray-800 text-sm mt-1">{{ item.ai_extra.work_impact }}</p></div>
    {% endif %}
    {% if item.ai_extra.get("entry_advice") %}
    <div><span class="text-xs text-gray-400">切入建议</span><p class="text-gray-800 text-sm mt-1">{{ item.ai_extra.entry_advice }}</p></div>
    {% endif %}
    {% if item.ai_extra.get("ai_approach") %}
    <div><span class="text-xs text-gray-400">AI 做法</span><p class="text-gray-800 text-sm mt-1">{{ item.ai_extra.ai_approach }}</p></div>
    {% endif %}
    {% if item.ai_extra.get("monetization") %}
    <div><span class="text-xs text-gray-400">变现路径</span><p class="text-gray-800 text-sm mt-1">{{ item.ai_extra.monetization }}</p></div>
    {% endif %}
    {% if item.ai_extra.get("fit_score") %}
    <p class="text-sm text-gray-500">适合度：<span class="font-medium text-blue-600">{{ item.ai_extra.fit_score }}</span></p>
    {% endif %}
  </div>
  {% endif %}

  {% if item.fetched_at %}
  <p class="text-xs text-gray-400 mt-6">抓取时间：{{ item.fetched_at.strftime("%Y-%m-%d %H:%M") }}</p>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 5: 在 main.py 中追加 item router**

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.web.routes import auth, home, category, item

app = FastAPI(title="News Platform", version="0.1.0")
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(category.router)
app.include_router(item.router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
```

- [ ] **Step 6: 运行测试**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v -k "test_item"
```

Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
cd /Users/daichao/news-platform && git add app/web/routes/item.py app/web/templates/item.html app/main.py tests/test_web.py && git commit -m "feat: item detail page with read/saved HTMX toggles"
```

---

## Task 5: FTS5 全文搜索

**Files:**
- Modify: `app/models/base.py`（追加 `_init_fts()`，并从 `init_db()` 调用）
- Create: `app/web/routes/search.py`
- Create: `app/web/templates/search.html`
- Modify: `app/main.py`
- Modify: `tests/test_web.py`（追加，含 FTS5 测试引擎初始化）

- [ ] **Step 1: 追加测试**

在 `tests/test_web.py` 文件末尾、`_seed()` 调用之后追加 FTS5 测试初始化块，以及搜索路由测试。

在 `_seed()` 的调用行 `_seed()` 之后追加（文件顶部 `_seed()` 调用处）：

```python
# 对测试引擎初始化 FTS5（与 app/models/base._init_fts 逻辑相同）
from sqlalchemy import text as _t
with _engine.connect() as _c:
    _c.execute(_t("CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(title, summary_zh, content='items', content_rowid='id')"))
    _c.execute(_t("INSERT OR IGNORE INTO items_fts(rowid, title, summary_zh) SELECT id, title, COALESCE(summary_zh,'') FROM items"))
    _c.commit()
```

在文件末尾追加测试：

```python
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
```

- [ ] **Step 2: 运行，确认失败**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v -k "test_search" 2>&1 | head -15
```

- [ ] **Step 3: 修改 app/models/base.py，追加 _init_fts 和更新 init_db**

在文件末尾（`get_db()` 函数之后）追加：

```python
from sqlalchemy import text as _sql_text


def _init_fts() -> None:
    with engine.connect() as conn:
        conn.execute(_sql_text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
                title, summary_zh, content='items', content_rowid='id'
            )
        """))
        conn.execute(_sql_text("""
            CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
                INSERT INTO items_fts(rowid, title, summary_zh)
                VALUES (new.id, new.title, COALESCE(new.summary_zh, ''));
            END
        """))
        conn.execute(_sql_text("""
            INSERT OR IGNORE INTO items_fts(rowid, title, summary_zh)
            SELECT id, title, COALESCE(summary_zh, '') FROM items
        """))
        conn.commit()
```

将 `init_db()` 函数修改为：

```python
def init_db() -> None:
    from app.models import item, push_log, run_log, source  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _init_fts()
```

- [ ] **Step 4: 创建 app/web/routes/search.py**

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.item import Item
from app.web.deps import check_auth, templates

router = APIRouter()
_SEARCH_LIMIT = 50


@router.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = "", db: Session = Depends(get_db)):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)

    items: list[Item] = []
    if q.strip():
        try:
            rows = db.execute(
                text("SELECT rowid FROM items_fts WHERE items_fts MATCH :q ORDER BY rank LIMIT :lim"),
                {"q": q.strip(), "lim": _SEARCH_LIMIT},
            ).fetchall()
            ids = [r[0] for r in rows]
            if ids:
                items = db.query(Item).filter(Item.id.in_(ids)).all()
        except Exception:
            items = []

    return templates.TemplateResponse(request, "search.html", {"q": q, "items": items})
```

- [ ] **Step 5: 创建 app/web/templates/search.html**

```html
{% extends "base.html" %}
{% block title %}搜索 · 资讯平台{% endblock %}
{% block content %}
<h1 class="text-xl font-bold mb-6">全文搜索</h1>
<form method="get" action="/search" class="flex gap-2 mb-6">
  <input type="text" name="q" value="{{ q }}" placeholder="输入关键词…"
         class="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
         autofocus />
  <button type="submit" class="bg-blue-600 text-white rounded-lg px-5 py-2 hover:bg-blue-700">搜索</button>
</form>

{% if q %}
  {% if items %}
    <p class="text-sm text-gray-500 mb-4">找到 {{ items|length }} 条结果</p>
    <div class="flex flex-col gap-2">
      {% for item in items %}
      <a href="/item/{{ item.id }}"
         class="bg-white rounded-lg border px-4 py-3 hover:shadow-sm transition">
        <div class="flex items-center gap-2">
          {% if item.is_key %}<span class="text-xs bg-red-500 text-white rounded px-1.5 py-0.5">重点</span>{% endif %}
          <span class="font-medium text-gray-900">{{ item.title }}</span>
        </div>
        {% if item.summary_zh %}
        <p class="text-sm text-gray-500 mt-1 line-clamp-1">{{ item.summary_zh }}</p>
        {% endif %}
      </a>
      {% endfor %}
    </div>
  {% else %}
    <p class="text-gray-400">没有找到与「{{ q }}」相关的内容</p>
  {% endif %}
{% endif %}
{% endblock %}
```

- [ ] **Step 6: 在 main.py 中追加 search router**

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.web.routes import auth, home, category, item, search

app = FastAPI(title="News Platform", version="0.1.0")
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(category.router)
app.include_router(item.router)
app.include_router(search.router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
```

- [ ] **Step 7: 运行测试**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v -k "test_search"
```

Expected: 3 passed

- [ ] **Step 8: Commit**

```bash
cd /Users/daichao/news-platform && git add app/models/base.py app/web/routes/search.py app/web/templates/search.html app/main.py tests/test_web.py && git commit -m "feat: FTS5 full-text search"
```

---

## Task 6: 归档页 + 晨晚报页

**Files:**
- Create: `app/web/routes/archive.py`
- Create: `app/web/templates/archive.html`
- Create: `app/web/templates/report.html`
- Modify: `app/main.py`
- Modify: `tests/test_web.py`（追加）

- [ ] **Step 1: 追加测试**

```python
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
```

- [ ] **Step 2: 运行，确认失败**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v -k "test_archive or test_report" 2>&1 | head -15
```

- [ ] **Step 3: 创建 app/web/routes/archive.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import cast, String, func, desc
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.item import Item
from app.models.push_log import PushLog
from app.web.deps import check_auth, templates

router = APIRouter()

_VALID_SLOTS = {"morning", "evening"}


@router.get("/archive", response_class=HTMLResponse)
async def archive(request: Request, db: Session = Depends(get_db)):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)

    date_counts = (
        db.query(
            cast(func.date(Item.fetched_at), String).label("d"),
            func.count(Item.id).label("cnt"),
        )
        .group_by("d")
        .order_by(desc("d"))
        .limit(90)
        .all()
    )
    return templates.TemplateResponse(request, "archive.html",
                                      {"date_counts": date_counts})


@router.get("/report/{slot}/{date}", response_class=HTMLResponse)
async def report(slot: str, date: str, request: Request, db: Session = Depends(get_db)):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    if slot not in _VALID_SLOTS:
        raise HTTPException(status_code=404, detail="无效的时段")

    logs = (
        db.query(PushLog)
        .filter(
            PushLog.slot == slot,
            cast(func.date(PushLog.pushed_at), String) == date,
        )
        .all()
    )
    item_ids: list[int] = []
    for log in logs:
        if log.item_ids:
            item_ids.extend(log.item_ids)

    items = db.query(Item).filter(Item.id.in_(item_ids)).all() if item_ids else []
    slot_label = {"morning": "早间", "evening": "晚间"}[slot]
    return templates.TemplateResponse(request, "report.html",
                                      {"slot_label": slot_label, "date": date, "items": items})
```

- [ ] **Step 4: 创建 app/web/templates/archive.html**

```html
{% extends "base.html" %}
{% block title %}归档 · 资讯平台{% endblock %}
{% block content %}
<h1 class="text-xl font-bold mb-6">📅 内容归档</h1>
{% if not date_counts %}
  <p class="text-gray-400">暂无内容</p>
{% else %}
<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
  {% for row in date_counts %}
  <div class="bg-white rounded-lg border p-4 hover:shadow-sm">
    <p class="font-medium text-gray-800">{{ row.d }}</p>
    <p class="text-sm text-gray-400 mt-1">{{ row.cnt }} 条内容</p>
    <div class="flex gap-3 mt-3 text-xs">
      <a href="/report/morning/{{ row.d }}" class="text-blue-500 hover:underline">早间报</a>
      <a href="/report/evening/{{ row.d }}" class="text-blue-500 hover:underline">晚间报</a>
    </div>
  </div>
  {% endfor %}
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: 创建 app/web/templates/report.html**

```html
{% extends "base.html" %}
{% block title %}{{ date }} {{ slot_label }}报 · 资讯平台{% endblock %}
{% block content %}
<h1 class="text-xl font-bold mb-2">{{ date }} · {{ slot_label }}资讯速报</h1>
<p class="text-sm text-gray-500 mb-6">共 {{ items|length }} 条内容</p>
{% if not items %}
  <p class="text-gray-400">本次暂无推送记录</p>
{% else %}
<div class="flex flex-col gap-2">
  {% for item in items %}
  <a href="/item/{{ item.id }}"
     class="bg-white rounded-lg border px-4 py-3 hover:shadow-sm transition">
    <div class="flex items-center gap-2">
      {% if item.is_key %}<span class="text-xs bg-red-500 text-white rounded px-1.5 py-0.5">重点</span>{% endif %}
      <span class="text-xs text-gray-400 shrink-0">{{ item.category_slug }}</span>
      <span class="font-medium text-gray-900">{{ item.title }}</span>
    </div>
    {% if item.summary_zh %}
    <p class="text-sm text-gray-500 mt-1 line-clamp-1">{{ item.summary_zh }}</p>
    {% endif %}
  </a>
  {% endfor %}
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 6: 在 main.py 中追加 archive router**

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.web.routes import auth, home, category, item, search, archive

app = FastAPI(title="News Platform", version="0.1.0")
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(category.router)
app.include_router(item.router)
app.include_router(search.router)
app.include_router(archive.router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
```

- [ ] **Step 7: 运行测试**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v -k "test_archive or test_report"
```

Expected: 5 passed

- [ ] **Step 8: Commit**

```bash
cd /Users/daichao/news-platform && git add app/web/routes/archive.py app/web/templates/archive.html app/web/templates/report.html app/main.py tests/test_web.py && git commit -m "feat: archive calendar + morning/evening report view"
```

---

## Task 7: 来源管理页

**Files:**
- Create: `app/web/routes/admin.py`
- Create: `app/web/templates/admin_sources.html`
- Modify: `app/main.py`
- Modify: `tests/test_web.py`（追加）

> 直接读写 `config.yaml`；开关 `enabled` 或修改 `feed_url` 后写回，并清空 `get_config` lru_cache。PyYAML 写回会丢失注释，单用户工具可接受。

- [ ] **Step 1: 追加测试**

```python
# ── Task 7: Admin sources 测试 ────────────────────────────────────────────────
def test_admin_sources_200(authed):
    resp = authed.get("/admin/sources")
    assert resp.status_code == 200
    assert "来源管理" in resp.text


def test_admin_sources_lists_sources(authed):
    resp = authed.get("/admin/sources")
    # config.yaml 中存在的 fetch_type 之一应出现在页面中
    assert any(t in resp.text for t in ("rss", "api_github", "api_hn", "api_ph", "api_hf", "scraper"))
```

- [ ] **Step 2: 运行，确认失败**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v -k "test_admin" 2>&1 | head -15
```

- [ ] **Step 3: 创建 app/web/routes/admin.py**

```python
from pathlib import Path
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import yaml

from app.config import get_config
from app.web.deps import check_auth, templates

router = APIRouter()
_CONFIG_PATH = "config.yaml"


def _load_raw() -> dict:
    return yaml.safe_load(Path(_CONFIG_PATH).read_text(encoding="utf-8"))


def _save_raw(data: dict) -> None:
    Path(_CONFIG_PATH).write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    get_config.cache_clear()


def _flat_sources(data: dict) -> list[dict]:
    sources = []
    for cat_idx, cat in enumerate(data.get("categories", [])):
        for src_idx, src in enumerate(cat.get("sources", [])):
            sources.append({
                "cat_slug": cat["slug"],
                "cat_name": cat["name"],
                "cat_index": cat_idx,
                "src_index": src_idx,
                "name": src.get("name", ""),
                "fetch_type": src.get("fetch_type", ""),
                "feed_url": src.get("feed_url", ""),
                "enabled": src.get("enabled", True),
            })
    return sources


@router.get("/admin/sources", response_class=HTMLResponse)
async def admin_sources(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    data = _load_raw()
    return templates.TemplateResponse(
        request, "admin_sources.html", {"sources": _flat_sources(data)}
    )


@router.post("/admin/sources/toggle")
async def toggle_source(
    request: Request,
    cat_index: int = Form(...),
    src_index: int = Form(...),
):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    data = _load_raw()
    src = data["categories"][cat_index]["sources"][src_index]
    src["enabled"] = not src.get("enabled", True)
    _save_raw(data)
    return RedirectResponse(url="/admin/sources", status_code=302)


@router.post("/admin/sources/url")
async def update_source_url(
    request: Request,
    cat_index: int = Form(...),
    src_index: int = Form(...),
    feed_url: str = Form(...),
):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    feed_url = feed_url.strip()
    if not feed_url:
        return RedirectResponse(url="/admin/sources", status_code=302)
    data = _load_raw()
    data["categories"][cat_index]["sources"][src_index]["feed_url"] = feed_url
    _save_raw(data)
    return RedirectResponse(url="/admin/sources", status_code=302)
```

- [ ] **Step 4: 创建 app/web/templates/admin_sources.html**

```html
{% extends "base.html" %}
{% block title %}来源管理 · 资讯平台{% endblock %}
{% block content %}
<h1 class="text-xl font-bold mb-6">⚙️ 来源管理</h1>
<div class="flex flex-col gap-3">
  {% set ns = namespace(prev_cat="") %}
  {% for s in sources %}
  {% if s.cat_slug != ns.prev_cat %}
  <h2 class="text-base font-semibold text-gray-700 mt-4 first:mt-0">{{ s.cat_name }}</h2>
  {% set ns.prev_cat = s.cat_slug %}
  {% endif %}
  <div class="bg-white rounded-lg border px-4 py-3 flex items-center gap-4">
    <form method="post" action="/admin/sources/toggle" class="shrink-0">
      <input type="hidden" name="cat_index" value="{{ s.cat_index }}" />
      <input type="hidden" name="src_index" value="{{ s.src_index }}" />
      <button type="submit"
              class="w-10 h-6 rounded-full relative transition-colors {{ 'bg-blue-500' if s.enabled else 'bg-gray-300' }}">
        <span class="absolute top-0.5 {{ 'right-0.5' if s.enabled else 'left-0.5' }} w-5 h-5 bg-white rounded-full shadow transition-all"></span>
      </button>
    </form>
    <div class="flex-1 min-w-0">
      <p class="font-medium text-gray-800 text-sm">
        {{ s.name }}
        <span class="ml-2 text-xs bg-gray-100 text-gray-500 rounded px-1.5 py-0.5">{{ s.fetch_type }}</span>
      </p>
      <form method="post" action="/admin/sources/url" class="flex gap-2 mt-1">
        <input type="hidden" name="cat_index" value="{{ s.cat_index }}" />
        <input type="hidden" name="src_index" value="{{ s.src_index }}" />
        <input type="text" name="feed_url" value="{{ s.feed_url }}"
               class="flex-1 text-xs text-gray-500 border-b border-transparent hover:border-gray-300 focus:border-blue-400 focus:outline-none bg-transparent py-0.5 min-w-0" />
        <button type="submit" class="text-xs text-blue-500 hover:text-blue-700 shrink-0">保存</button>
      </form>
    </div>
  </div>
  {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 5: 在 main.py 中追加 admin router（最终版本）**

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.web.routes import auth, home, category, item, search, archive, admin

app = FastAPI(title="News Platform", version="0.1.0")
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(category.router)
app.include_router(item.router)
app.include_router(search.router)
app.include_router(archive.router)
app.include_router(admin.router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
```

- [ ] **Step 6: 运行测试**

```bash
cd /Users/daichao/news-platform && pytest tests/test_web.py -v -k "test_admin"
```

Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
cd /Users/daichao/news-platform && git add app/web/routes/admin.py app/web/templates/admin_sources.html app/main.py tests/test_web.py && git commit -m "feat: admin sources page with toggle/url edit"
```

---

## Task 8: 全量验收

- [ ] **Step 1: 运行全部测试**

```bash
cd /Users/daichao/news-platform && pytest tests/ -v --tb=short
```

Expected: ≥ 46 tests pass（36 原有 + ≥ 16 新增 web 测试）

- [ ] **Step 2: 验证 FastAPI app 可正常启动**

```bash
cd /Users/daichao/news-platform && uvicorn app.main:app --port 8002 --log-level warning &
sleep 2 && curl -s http://localhost:8002/health && kill %1
```

Expected: `{"status":"ok"}`

- [ ] **Step 3: 验证所有 web 路由均已注册**

```bash
cd /Users/daichao/news-platform && python -c "
from app.main import app
paths = [r.path for r in app.routes]
required = ['/login', '/logout', '/', '/category/{slug}', '/item/{item_id}',
            '/item/{item_id}/toggle', '/search', '/archive',
            '/report/{slot}/{date}', '/admin/sources']
for r in required:
    print('OK' if r in paths else 'MISSING', r)
"
```

Expected: 全部输出 `OK`

- [ ] **Step 4: 验证无 Optional/List 引入**

```bash
cd /Users/daichao/news-platform && grep -rn "Optional\[" app/web/ app/models/base.py 2>/dev/null && echo "FAIL: Optional found" || echo "PASS: no Optional"
```

Expected: `PASS: no Optional`

- [ ] **Step 5: 最终 Commit**

```bash
cd /Users/daichao/news-platform && git status && git commit -m "feat: Plan 2 complete — full web frontend" --allow-empty
```

---

## 验收标准

```bash
# 全部测试通过（≥46）
pytest tests/ -v

# FastAPI 启动并返回 health
uvicorn app.main:app --port 8000 &
curl http://localhost:8000/health  # → {"status":"ok"}

# 所有路由注册
python -c "from app.main import app; print([r.path for r in app.routes])"
# 预期含: /login /logout / /category/{slug} /item/{item_id} /search /archive /report/{slot}/{date} /admin/sources
```

**Plan 3（Docker + Nginx + 部署）** 在本 Plan 验收后编写。
