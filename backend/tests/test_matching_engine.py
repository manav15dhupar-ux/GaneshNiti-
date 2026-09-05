"""
test_matching_engine.py — tests the financing-fit ranking logic against the
exact 3 demo test cases from the project roadmap.

Run with:
    pytest tests/test_matching_engine.py -v
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.eligibility_engine import check_all_schemes
from services.matching_engine import rank_schemes

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "schemes_preview.json"


def load_schemes():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_demo_case_small_amount_ranks_micro_credit_first():
    """Roadmap demo case 1: SC, Maharashtra, 2.8L income, needs 1.2L for
    equipment. Micro Credit Finance should rank ABOVE Term Loan, even though
    Term Loan could technically also cover this amount -- because it's a
    much tighter, more appropriate fit."""
    schemes = load_schemes()
    user = {
        "category": "SC", "annual_income": 280000, "business_type": "tailoring",
        "purpose": "equipment purchase", "amount_required": 120000, "is_new_business": False,
    }
    eligibility_results = check_all_schemes(user, schemes)
    ranked = rank_schemes(user, schemes, eligibility_results)

    top = ranked[0]
    assert top.scheme_id == "NSFDC008"  # Micro Credit Finance
    assert top.eligible is True
    assert top.match_score > 0


def test_demo_case_ineligible_shows_zero_score_not_hidden():
    """Roadmap demo case 2: General category, 15L income -- should appear
    in results with score 0 and full trace, not be silently dropped."""
    schemes = load_schemes()
    user = {
        "category": "General", "annual_income": 1500000, "business_type": "trading",
        "purpose": "working capital", "amount_required": 500000, "is_new_business": False,
    }
    eligibility_results = check_all_schemes(user, schemes)
    ranked = rank_schemes(user, schemes, eligibility_results)

    nsfdc_results = [r for r in ranked if r.scheme_id in ("NSFDC007", "NSFDC008", "NSFDC009")]
    for r in nsfdc_results:
        assert r.eligible is False
        assert r.match_score == 0
        assert len(r.trace) > 0  # reason is still visible, not hidden


def test_demo_case_large_amount_ranks_term_loan_first():
    """Roadmap demo case 3: large amount should rank Term Loan above Micro
    Credit Finance (which would fail eligibility outright for this amount)."""
    schemes = load_schemes()
    user = {
        "category": "SC", "annual_income": 250000, "business_type": "manufacturing unit",
        "purpose": "equipment/machinery purchase", "amount_required": 4000000, "is_new_business": False,
    }
    eligibility_results = check_all_schemes(user, schemes)
    ranked = rank_schemes(user, schemes, eligibility_results)

    eligible_ranked = [r for r in ranked if r.eligible]
    assert eligible_ranked[0].scheme_id == "NSFDC007"  # Term Loan


def test_score_breakdown_is_explainable():
    """Confirms every eligible result carries a transparent breakdown --
    the whole point of financing-fit scoring is that it's NOT a black box."""
    schemes = load_schemes()
    user = {
        "category": "SC", "annual_income": 280000, "business_type": "tailoring",
        "purpose": "equipment purchase", "amount_required": 120000, "is_new_business": False,
    }
    eligibility_results = check_all_schemes(user, schemes)
    ranked = rank_schemes(user, schemes, eligibility_results)

    top = ranked[0]
    assert set(top.score_breakdown.keys()) == {"amount_fit", "purpose_match", "category_match", "business_stage"}
    assert sum(top.score_breakdown.values()) == top.match_score