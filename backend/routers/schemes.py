"""
routers/schemes.py — read-only data endpoints.

    GET /schemes            the verified NSFDC scheme records the engine uses
    GET /channel-partners   the (simulated) Channel Partner records

Both report where the data came from: "firestore" when a live connection is
configured, otherwise "local_json" (the bundled fallback in backend/data/).
The /recommend endpoint lives in routers/recommend.py.
"""

from fastapi import APIRouter

from services.firestore_client import get_all_schemes, get_all_channel_partners, is_using_live_firestore

router = APIRouter()


def _source():
    return "firestore" if is_using_live_firestore() else "local_json"


@router.get("/schemes")
def list_schemes():
    schemes = get_all_schemes()          # reading first lets the client decide Firestore vs fallback
    return {"source": _source(), "count": len(schemes), "schemes": schemes}


@router.get("/channel-partners")
def list_channel_partners():
    partners = get_all_channel_partners()
    return {"source": _source(), "count": len(partners), "partners": partners}
