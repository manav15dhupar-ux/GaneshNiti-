"""
partner_locator.py — Day 5, first deliverable.

WHAT THIS DOES:
Given a matched scheme and the user's state, finds Channel Partners that
handle that scheme, preferring an exact state match. This is the "last mile"
feature that myScheme has no equivalent of.

IMPORTANT -- SAY THIS OUT LOUD IN YOUR DEMO:
All Channel Partner data is SIMULATED. Real-time partner availability, fund
utilization status, and NPA data are not publicly available -- this was a
deliberate, documented scope decision made early in the project, not an
oversight. Never present this data as live.

HOW TO TEST:
    pytest tests/test_partner_locator.py -v
"""

import re
from typing import Optional

# Words to ignore when comparing scheme names -- "Scheme" and category
# suffixes like "(Scheduled Castes)" vary between how schemes.py stores the
# full official name and how channel_partners.py lists shorthand names, so
# an exact string match would silently return zero results. Caught while
# building Day 5 by checking the real data, not just an isolated unit test.
_IGNORE_WORDS = {"scheme", "the", "of", "for", "and"}


def _scheme_keywords(name: str) -> set:
    cleaned = re.sub(r"\([^)]*\)", "", name)  # drop "(Scheduled Castes)" style suffixes
    words = re.findall(r"[a-z]+", cleaned.lower())
    return {w for w in words if w not in _IGNORE_WORDS and len(w) > 2}


def find_matching_partners(scheme_name: str, user_state: Optional[str], partners: list, limit: int = 3) -> list:
    """
    Returns up to `limit` Channel Partners that handle the given scheme,
    ranked with an exact state match first, then any other partner handling
    the scheme (since a user may need to travel to a partner in another
    district/state if none exist locally in this simulated dataset).

    Matches on shared keywords rather than exact string equality, since the
    same scheme is named slightly differently in scheme records ("NSFDC
    Micro Credit Finance Scheme") vs. partner records ("NSFDC Micro Credit
    Finance") -- see _scheme_keywords() above.
    """
    target_words = _scheme_keywords(scheme_name)

    def handles_scheme(partner):
        for handled in (partner.get("schemesHandled") or []):
            handled_words = _scheme_keywords(handled)
            # require meaningful overlap, not just one shared generic word
            if len(target_words & handled_words) >= 2:
                return True
        return False

    handling_scheme = [p for p in partners if handles_scheme(p)]

    if not handling_scheme:
        return []

    if user_state:
        same_state = [p for p in handling_scheme if (p.get("state") or "").strip().lower() == user_state.strip().lower()]
        other_state = [p for p in handling_scheme if p not in same_state]
        ordered = same_state + other_state
    else:
        ordered = handling_scheme

    return ordered[:limit]


def format_partner_summary(partner: dict) -> dict:
    """Shapes a partner record for the API response -- includes a checklist-
    style next-step hint, and ALWAYS flags the data as simulated."""
    return {
        "partnerName": partner.get("partnerName"),
        "partnerType": partner.get("partnerType"),
        "state": partner.get("state"),
        "district": partner.get("district"),
        "address": partner.get("address"),
        "contactNumber": partner.get("contactNumber"),
        "isSimulatedData": True,
    }