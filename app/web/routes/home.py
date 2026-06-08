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
