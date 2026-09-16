"""FastAPI アプリケーション（設計書 17.4）。"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import convert, projects


def _base_dir() -> Path:
    """通常実行時はリポジトリのルート、PyInstallerでのスタンドアロン実行時は展開先を返す。"""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled)
    return Path(__file__).resolve().parents[1]


FRONTEND_DIST = _base_dir() / "frontend" / "dist"

app = FastAPI(title="Guitar TAB Maker", version="1.0.0")

# Vite の開発サーバー（http://localhost:5173）から叩けるようにする
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(convert.router)
app.include_router(projects.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
