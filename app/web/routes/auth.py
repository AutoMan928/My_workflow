import os
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.deps import COOKIE_NAME, COOKIE_MAX_AGE, check_auth, make_session_cookie, templates

router = APIRouter()
_SITE_PASSWORD = os.environ["SITE_PASSWORD"]


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
                    max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax")
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(COOKIE_NAME)
    return resp
