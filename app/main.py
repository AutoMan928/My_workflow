from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.web.routes import auth, home, category, item, search, archive, admin, report


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.models.base import init_db
    init_db()
    yield


app = FastAPI(title="News Platform", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(category.router)
app.include_router(item.router)
app.include_router(search.router)
app.include_router(archive.router)
app.include_router(admin.router)
app.include_router(report.router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
