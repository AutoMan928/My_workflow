from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.item import Item
from app.web.deps import check_auth, templates
from app.web.utils import since_utc

router = APIRouter()

_PAGE_SIZE = 20
_FOLD_THRESHOLD = 5.5  # score below this gets folded into collapsible section

_CATEGORY_LABELS = {
    "banking": "银行用户运营",
    "tech": "技术与AI工具",
    "startup": "个人创业",
    "hualong": "画龙科技监控",
    "github_trending": "GitHub 热门趋势",
}

_PERIOD_DAYS = {"today": 1, "week": 7, "month": 30}


@router.get("/category/{slug}", response_class=HTMLResponse)
async def category_page(
    slug: str,
    request: Request,
    page: int = 0,
    only_key: bool = False,
    period: str = "",
    db: Session = Depends(get_db),
):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    if slug not in _CATEGORY_LABELS:
        raise HTTPException(status_code=404, detail="类别不存在")

    query = db.query(Item).filter(Item.category_slug == slug)
    if only_key:
        query = query.filter(Item.is_key.is_(True))

    summary_mode = period in _PERIOD_DAYS
    if summary_mode:
        # Time-range summary: filter by date, sort by score descending
        query = query.filter(Item.fetched_at >= since_utc(_PERIOD_DAYS[period]))
        all_rows = query.order_by(desc(Item.score)).all()
    else:
        # Timeline mode: sort by fetched_at descending, paginate
        all_rows = query.order_by(desc(Item.fetched_at)).all()

    # Split into key/normal (visible) vs low-score (folded)
    visible = [x for x in all_rows if x.is_key or (x.score or 0) >= _FOLD_THRESHOLD]
    folded = [x for x in all_rows if not x.is_key and (x.score or 0) < _FOLD_THRESHOLD]

    has_more = len(visible) > (page + 1) * _PAGE_SIZE
    items = visible[page * _PAGE_SIZE: (page + 1) * _PAGE_SIZE]

    ctx = {
        "slug": slug,
        "label": _CATEGORY_LABELS[slug],
        "items": items,
        "folded_items": folded if page == 0 else [],
        "page": page,
        "next_page": page + 1,
        "has_more": has_more,
        "only_key": only_key,
        "period": period,
        "summary_mode": summary_mode,
    }

    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(request, "_items_partial.html", ctx)
    return templates.TemplateResponse(request, "category.html", ctx)
