import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.item import Item
from app.web.deps import check_auth, templates

router = APIRouter()
_SEARCH_LIMIT = 50
logger = logging.getLogger(__name__)


@router.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = "", db: Session = Depends(get_db)):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)

    items: list[Item] = []
    q_clean = q.strip()
    if q_clean:
        try:
            rows = db.execute(
                text("SELECT rowid FROM items_fts WHERE items_fts MATCH :q ORDER BY rank LIMIT :lim"),
                {"q": q_clean + "*", "lim": _SEARCH_LIMIT},
            ).fetchall()
            ids = [r[0] for r in rows]
            if ids:
                items = db.query(Item).filter(Item.id.in_(ids)).all()
        except Exception as exc:
            logger.warning("FTS5 search failed for %r, falling back to LIKE: %s", q_clean, exc)
            pattern = f"%{q_clean}%"
            title_zh_col = func.json_extract(Item.ai_extra, "$.title_zh")
            items = (
                db.query(Item)
                .filter(
                    or_(
                        Item.title.ilike(pattern),
                        title_zh_col.ilike(pattern),
                    )
                )
                .limit(_SEARCH_LIMIT)
                .all()
            )

    return templates.TemplateResponse(request, "search.html", {"q": q, "items": items})
