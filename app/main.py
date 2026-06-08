from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.web.routes import auth, home, category, item

app = FastAPI(title="News Platform", version="0.1.0")
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(category.router)
app.include_router(item.router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
