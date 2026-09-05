"""
firestore_client.py — connects to Firestore, and safely falls back to local
JSON files if Firestore isn't reachable (no credentials yet, no internet,
wrong project, etc). This means your backend NEVER crashes just because
Firebase isn't fully set up yet — it just uses the last-known-good data.

WHY THIS MATTERS FOR A BEGINNER TEAM:
On Day 2, not everyone will have Firebase credentials configured yet, and
during the hackathon itself, WiFi problems happen. This file means the rest
of the team (frontend, eligibility engine) can keep working against real
schemes data even before Firestore is fully wired up.
"""

import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCHEMES_FALLBACK = DATA_DIR / "schemes_preview.json"
PARTNERS_FALLBACK = DATA_DIR / "channel_partners_preview.json"

_firestore_client = None
_firestore_available = False


def _try_connect():
    """Attempts to connect to Firestore using a service account key.
    Returns the Firestore client, or None if anything goes wrong."""
    global _firestore_client, _firestore_available

    cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")
    if not Path(cred_path).exists():
        print(f"[firestore_client] No credentials file at '{cred_path}' -- using local JSON fallback.")
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

        client = firestore.client()
        _firestore_available = True
        print("[firestore_client] Connected to Firestore successfully.")
        return client
    except Exception as e:
        print(f"[firestore_client] Could not connect to Firestore ({e}) -- using local JSON fallback.")
        return None


def get_firestore_client():
    """Returns a cached Firestore client, connecting on first use."""
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = _try_connect()
    return _firestore_client


def get_all_schemes():
    """Returns a list of scheme dicts, from Firestore if available,
    otherwise from the local fallback JSON file."""
    client = get_firestore_client()
    if client:
        try:
            docs = client.collection("schemes").stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"[firestore_client] Firestore read failed ({e}) -- falling back to local JSON.")

    if SCHEMES_FALLBACK.exists():
        with open(SCHEMES_FALLBACK, encoding="utf-8") as f:
            return json.load(f)
    return []


def get_all_channel_partners():
    """Same idea as get_all_schemes(), but for channel_partners."""
    client = get_firestore_client()
    if client:
        try:
            docs = client.collection("channel_partners").stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"[firestore_client] Firestore read failed ({e}) -- falling back to local JSON.")

    if PARTNERS_FALLBACK.exists():
        with open(PARTNERS_FALLBACK, encoding="utf-8") as f:
            return json.load(f)
    return []


def is_using_live_firestore():
    """Lets other parts of the app (or the /health endpoint) report
    whether they're currently reading real Firestore data or fallback data."""
    return _firestore_available