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
    try:
        db.commit()
        db.refresh(item)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="数据库错误")
    is_on = getattr(item, field)
    btn_text = ("已读" if is_on else "标为已读") if field == "is_read" else ("已收藏" if is_on else "收藏")
    btn_class = "bg-gray-700 text-white" if is_on else "bg-white text-gray-700 border"
    return HTMLResponse(
        f'<button hx-post="/item/{item_id}/toggle" hx-vals=\'{{"field":"{field}"}}\' '
        f'hx-target="this" hx-swap="outerHTML" '
        f'class="rounded px-3 py-1 text-sm {btn_class}">{btn_text}</button>'
    )
