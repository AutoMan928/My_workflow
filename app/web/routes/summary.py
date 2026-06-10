"""Weekly and monthly summary view — top items across all categories."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.item import Item
from app.web.deps import check_auth, templates
from app.web.utils import since_utc, cst_date_n_days_ago, cst_today

router = APIRouter()

_CATEGORY_META = {
    "banking":         "银行用户运营",
    "tech":            "技术与 AI 工具",
    "startup":         "创业洞察",
    "hualong":         "画龙科技监控",
    "github_trending": "GitHub 热门趋势",
}
_TOP_N = 10


@router.get("/summary", response_class=HTMLResponse)
async def summary_page(
    request: Request,
    period: str = "week",
    db: Session = Depends(get_db),
):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)

    if period == "month":
        days_back = 30
        period_label = "近一个月"
    else:
        period = "week"
        days_back = 7
        period_label = "近一周"

    since_dt = since_utc(days_back)
    since_display = cst_date_n_days_ago(days_back)

    sections = []
    for slug, label in _CATEGORY_META.items():
        items = (
            db.query(Item)
            .filter(Item.category_slug == slug, Item.fetched_at >= since_dt)
            .order_by(desc(Item.score))
            .limit(_TOP_N)
            .all()
        )
        total = (
            db.query(Item)
            .filter(Item.category_slug == slug, Item.fetched_at >= since_dt)
            .count()
        )
        if total > 0:
            sections.append({
                "slug": slug,
                "label": label,
                "top_items": items,
                "total": total,
            })

    return templates.TemplateResponse(request, "summary.html", {
        "sections": sections,
        "period": period,
        "period_label": period_label,
        "since": since_display,
        "today": cst_today(),
    })
