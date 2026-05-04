import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_DEV_UI = r"https?://.*:(5173|3000)$"


def _extra_allowed_origins() -> list[str]:
    raw = (os.environ.get("CORS_ALLOWED_ORIGINS") or "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def setup_cors(app: FastAPI) -> None:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        *_extra_allowed_origins(),
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=_DEV_UI,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
