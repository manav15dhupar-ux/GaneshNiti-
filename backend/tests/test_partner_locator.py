"""
test_partner_locator.py — tests the Channel Partner locator against the real
simulated partner dataset.

Run with:
    pytest tests/test_partner_locator.py -v
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.partner_locator import find_matching_partners, format_partner_summary

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "channel_partners_preview.json"


def load_partners():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_finds_partner_in_same_state_first():
    partners = load_partners()
    # Uses the FULL official scheme name (as stored in schemes_preview.json),
    # not the shorthand used in partner records -- this is the exact
    # mismatch that was a real bug until the keyword-based matching fix.
    results = find_matching_partners("NSFDC Term Loan Scheme (Scheduled Castes)", "Maharashtra", partners)
    assert len(results) > 0, "Should find partners even though scheme names differ in wording"
    assert results[0]["state"] == "Maharashtra"


def test_finds_partner_with_full_scheme_name_not_just_shorthand():
    """Regression test for the exact bug found in Day 5: schemes.py stores
    'NSFDC Micro Credit Finance Scheme', partner records store 'NSFDC Micro
    Credit Finance' -- these must still match."""
    partners = load_partners()
    results = find_matching_partners("NSFDC Micro Credit Finance Scheme", "Maharashtra", partners)
    assert len(results) > 0, "Full scheme name (with 'Scheme' suffix) must still match partner records"


def test_no_match_returns_empty_list_not_error():
    partners = load_partners()
    results = find_matching_partners("A Scheme That Does Not Exist", "Kerala", partners)
    assert results == []


def test_respects_limit():
    partners = load_partners()
    results = find_matching_partners("NSFDC Term Loan", None, partners, limit=2)
    assert len(results) <= 2


def test_summary_always_flags_simulated():
    partners = load_partners()
    if partners:
        summary = format_partner_summary(partners[0])
        assert summary["isSimulatedData"] is True