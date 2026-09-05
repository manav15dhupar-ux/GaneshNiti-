"""
main.py — Day 4 version. Adds the /recommend endpoint on top of everything
built in Day 2 and Day 3.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import schemes, recommend

app = FastAPI(title="PS92 Scheme Navigator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schemes.router)
app.include_router(recommend.router)


@app.get("/")
def read_root():
    return {"message": "PS92 backend is running. Try /schemes, /health, or POST /recommend."}


@app.get("/health")
def health_check():
    return {"status": "ok"}