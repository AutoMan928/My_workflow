import logging
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import yaml

from app.config import get_config
from app.web.deps import check_auth, templates

logger = logging.getLogger(__name__)


def _do_run_pipeline(slot: str) -> None:
    try:
        Path("data").mkdir(exist_ok=True)
        from app.models.base import SessionLocal
        from app.scheduler.pipeline import run_pipeline
        cfg = get_config()
        db = SessionLocal()
        try:
            summary = run_pipeline(slot, cfg.categories, db, cfg)
            logger.info("Admin-triggered pipeline (%s) done: %s", slot, summary)
        finally:
            db.close()
    except Exception as exc:
        logger.error("Admin pipeline run (%s) failed: %s", slot, exc)

router = APIRouter()
_CONFIG_PATH = "config.yaml"


def _load_raw() -> dict:
    try:
        content = Path(_CONFIG_PATH).read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {"categories": []}
    except yaml.YAMLError:
        return {"categories": []}


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
    cats = data.get("categories", [])
    if not (0 <= cat_index < len(cats)):
        return RedirectResponse(url="/admin/sources", status_code=302)
    if not (0 <= src_index < len(cats[cat_index].get("sources", []))):
        return RedirectResponse(url="/admin/sources", status_code=302)
    src = cats[cat_index]["sources"][src_index]
    src["enabled"] = not src.get("enabled", True)
    data["categories"] = cats
    _save_raw(data)
    return RedirectResponse(url="/admin/sources", status_code=302)


@router.post("/admin/run-pipeline")
async def admin_run_pipeline(
    request: Request,
    background_tasks: BackgroundTasks,
    slot: str = Form("morning"),
):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    background_tasks.add_task(_do_run_pipeline, slot)
    return RedirectResponse(url="/admin/sources?triggered=1", status_code=302)


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
    cats = data.get("categories", [])
    if not (0 <= cat_index < len(cats)):
        return RedirectResponse(url="/admin/sources", status_code=302)
    if not (0 <= src_index < len(cats[cat_index].get("sources", []))):
        return RedirectResponse(url="/admin/sources", status_code=302)
    cats[cat_index]["sources"][src_index]["feed_url"] = feed_url
    data["categories"] = cats
    _save_raw(data)
    return RedirectResponse(url="/admin/sources", status_code=302)
