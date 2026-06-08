from datetime import date as date_type, datetime, time as _time

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

    try:
        target = date_type.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的日期格式，请使用 YYYY-MM-DD")

    start_dt = datetime.combine(target, _time.min)
    end_dt = datetime.combine(target, _time.max)
    logs = (
        db.query(PushLog)
        .filter(
            PushLog.slot == slot,
            PushLog.pushed_at >= start_dt,
            PushLog.pushed_at <= end_dt,
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
