from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.item import Item
from app.web.deps import check_auth, templates

router = APIRouter()

_CATEGORY_META = {
    "banking": {
        "label": "银行用户运营",
        "insight_field": "work_impact",
        "insight_label": "工作参考",
    },
    "tech": {
        "label": "技术与 AI 工具",
        "insight_field": "tool_use_case",
        "insight_label": "使用场景",
    },
    "startup": {
        "label": "创业洞察",
        "insight_field": "entry_advice",
        "insight_label": "切入建议",
    },
    "hualong": {
        "label": "画龙科技监控",
        "insight_field": "impact_zh",
        "insight_label": "影响评估",
    },
    "github_trending": {
        "label": "GitHub 热门趋势",
        "insight_field": "tool_use_case",
        "insight_label": "使用场景",
    },
}

_TOP_N = 6


@router.get("/daily", response_class=HTMLResponse)
async def daily_report(
    request: Request,
    day: str | None = None,
    db: Session = Depends(get_db),
):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)

    if day:
        try:
            report_date = date.fromisoformat(day)
        except ValueError:
            report_date = date.today()
    else:
        report_date = date.today()

    next_day = report_date + timedelta(days=1)

    sections = []
    for slug, meta in _CATEGORY_META.items():
        items = (
            db.query(Item)
            .filter(
                Item.category_slug == slug,
                Item.fetched_at >= report_date,
                Item.fetched_at < next_day,
            )
            .order_by(desc(Item.score))
            .limit(_TOP_N)
            .all()
        )

        total_today = (
            db.query(Item)
            .filter(
                Item.category_slug == slug,
                Item.fetched_at >= report_date,
                Item.fetched_at < next_day,
            )
            .count()
        )

        sections.append({
            "slug": slug,
            "meta": meta,
            "rows": items,
            "key_count": sum(1 for i in items if i.is_key),
            "total": total_today,
        })

    has_content = any(s["total"] > 0 for s in sections)

    return templates.TemplateResponse(
        request,
        "report.html",
        {
            "sections": sections,
            "report_date": report_date,
            "has_content": has_content,
            "prev_date": (report_date - timedelta(days=1)).isoformat(),
            "next_date": (report_date + timedelta(days=1)).isoformat() if report_date < date.today() else None,
        },
    )
