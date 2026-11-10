"""
main.py — FastAPI entrypoint for GaneshNiti.

One process serves both the JSON API and the static frontend, so a single
deployment (Render, Railway, Fly, any Docker host) is enough and the browser
never has to deal with CORS or a hard-coded backend URL.

Environment variables (all optional):
    OPENROUTER_API_KEY        enables LLM text -> structured-profile extraction.
                              Without it the app still works using the form fields.
    OPENROUTER_MODEL          override the default model
    FIREBASE_CREDENTIALS_PATH path to a service-account JSON file
    FIREBASE_CREDENTIALS_JSON the same JSON pasted as a string (for hosts with no files)
    ALLOWED_ORIGINS           comma-separated origins allowed to call the API
                              from another site (e.g. a GitHub Pages frontend).
                              Defaults to none, because same-origin needs no CORS.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import schemes, recommend

app = FastAPI(title="GaneshNiti — NSFDC Scheme Navigator")

_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

app.include_router(schemes.router)
app.include_router(recommend.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Serve the frontend from the same origin. Mounted last so API routes win.
# Local layout: <repo>/backend/main.py and <repo>/frontend; in Docker: /app/backend and /app/frontend.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
