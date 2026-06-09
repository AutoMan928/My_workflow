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
    "hualong": "画龙科技监控",
    "github_trending": "GitHub 热门趋势",
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
