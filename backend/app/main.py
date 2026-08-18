from __future__ import annotations

from pathlib import Path

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import APP_NAME, BASE_DIR, DATABASE_URL, DB_SCHEMA
from .db import init_db
from .routers import data, formats, reports, uploads

app = FastAPI(title=APP_NAME, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # internal tool, no auth by request
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(uploads.router)
app.include_router(data.router)
app.include_router(reports.router)
app.include_router(formats.router)


log = logging.getLogger("report-studio")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Say what actually broke.

    An unhandled error reached the browser as a bare "500 Request failed",
    which is unactionable for whoever hits it and for whoever is asked to fix
    it. This is an internal tool with no public surface, so the exception type
    and message are worth far more in the response than they cost.
    """
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"{type(exc).__name__}: {exc}",
            "where": f"{request.method} {request.url.path}",
            "traceback": traceback.format_exc()[-1500:],
        },
    )


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": APP_NAME,
        "database": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
        "schema": DB_SCHEMA,
    }


# Serve the built React app when it exists (npm run build in frontend/).
_dist = BASE_DIR.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        target = _dist / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(_dist / "index.html")
