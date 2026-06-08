from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from app.web.routes import auth
from app.web.deps import check_auth

app = FastAPI(title="News Platform", version="0.1.0")
app.include_router(auth.router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/")
async def index(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse({"status": "ok"})
