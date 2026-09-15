from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from app.db import get_connection, init_db
from app.routers import admin, assignments, auth, cases, moods, notifications, tasks
from seed import ensure_demo_data, seed_if_empty

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
LANDING_DIR = FRONTEND_DIR / "landing"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    try:
        init_db()
        conn = get_connection()
        try:
            seed_if_empty(conn)
            ensure_demo_data(conn)
        finally:
            conn.close()
    except Exception:
        # Surface full traceback in Zeabur / container logs
        import traceback

        traceback.print_exc()
        raise
    yield


app = FastAPI(title="Perfect Co-parenting API", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(cases.router)
app.include_router(moods.router)
app.include_router(assignments.router)
app.include_router(tasks.router)
app.include_router(notifications.router)


def _safe_landing_file(*parts: str) -> Path:
    candidate = (LANDING_DIR.joinpath(*parts)).resolve()
    root = LANDING_DIR.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return candidate


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/app")
def serve_app_redirect() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=307)


@app.get("/landing/css/{filename}")
def serve_landing_css(filename: str) -> FileResponse:
    return FileResponse(_safe_landing_file("css", Path(filename).name))


@app.get("/landing/js/{filename}")
def serve_landing_js(filename: str) -> FileResponse:
    return FileResponse(_safe_landing_file("js", Path(filename).name))


@app.get("/landing/assets/{filename}")
def serve_landing_assets(filename: str) -> FileResponse:
    return FileResponse(_safe_landing_file("assets", Path(filename).name))


@app.get("/fonts/{filename}")
def serve_font(filename: str) -> FileResponse:
    safe = Path(filename).name
    path = FRONTEND_DIR / "fonts" / safe
    if path.suffix.lower() != ".woff2" or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type="font/woff2")


@app.get("/styles.css")
def serve_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "styles.css")


@app.get("/app.js")
def serve_app_js() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "app.js")


@app.get("/login.js")
def serve_login_js() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "login.js")


@app.get("/img/{filename}")
def serve_img(filename: str) -> FileResponse:
    safe = Path(filename).name
    stem = Path(safe).stem
    suffix = Path(safe).suffix
    bases = (
        FRONTEND_DIR.parent / "mood_img",
        FRONTEND_DIR.parent / "task_img",
        FRONTEND_DIR / "img",
        FRONTEND_DIR.parent / "img",
    )
    names = [safe]
    if stem.startswith("mood-"):
        bare = stem.removeprefix("mood-")
        names.append(f"{bare}{suffix}")
        names.append(f"{bare}.png")
    for base in bases:
        for name in names:
            exact = base / name
            if exact.is_file():
                return FileResponse(exact)
        for name_stem in names:
            check_stem = Path(name_stem).stem
            for ext in (".jpg", ".jpeg", ".png", ".webp", ".svg"):
                path = base / f"{check_stem}{ext}"
                if path.is_file():
                    return FileResponse(path)
    raise HTTPException(status_code=404, detail="Image not found")
