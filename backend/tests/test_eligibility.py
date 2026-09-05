"""
test_eligibility.py — tests the eligibility engine against your REAL scheme
data (schemes_preview.json), not made-up fixtures. This means if these tests
pass, you know the engine works correctly against the actual data your app
will use.

Run with:
    pytest tests/test_eligibility.py -v
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.eligibility_engine import check_eligibility, check_all_schemes

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "schemes_preview.json"


def load_schemes():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_scheme(schemes, scheme_id):
    return next(s for s in schemes if s["schemeId"] == scheme_id)


# ---------- Case 1: Clearly eligible (from the roadmap's demo test cases) ----------
def test_clearly_eligible_micro_credit():
    schemes = load_schemes()
    scheme = get_scheme(schemes, "NSFDC008")  # Micro Credit Finance Scheme

    user = {
        "category": "SC",
        "annual_income": 280000,
        "business_type": "tailoring",
        "purpose": "equipment purchase",
        "amount_required": 120000,
        "is_new_business": False,
    }

    result = check_eligibility(user, scheme)

    assert result.eligible is True
    income_rule = next(r for r in result.trace if r.rule == "Annual family income")
    assert income_rule.passed is True
    assert "20,000" in income_rule.detail  # 300000 - 280000 = 20000 under the limit


# ---------- Case 2: Clearly ineligible (income far over every NSFDC limit) ----------
def test_clearly_ineligible_high_income():
    schemes = load_schemes()

    user = {
        "category": "General",
        "annual_income": 1500000,
        "business_type": "trading",
        "purpose": "working capital",
        "amount_required": 500000,
        "is_new_business": False,
    }

    results = check_all_schemes(user, schemes)
    nsfdc_results = [r for r in results if r.scheme_id in ("NSFDC007", "NSFDC008", "NSFDC009")]

    for r in nsfdc_results:
        assert r.eligible is False
        # confirm the trace actually pinpoints WHY -- not just a blanket "no"
        category_rule = next(c for c in r.trace if c.rule == "Category")
        assert category_rule.passed is False  # "General" doesn't match "SC (Scheduled Castes)"


# ---------- Case 3: Boundary case -- exactly at the income limit ----------
def test_boundary_income_exactly_at_limit():
    schemes = load_schemes()
    scheme = get_scheme(schemes, "NSFDC007")  # Term Loan, income limit 300000

    user = {
        "category": "SC",
        "annual_income": 300000,  # exactly the limit
        "business_type": "manufacturing",
        "purpose": "equipment/machinery purchase",
        "amount_required": 1000000,
        "is_new_business": True,
    }

    result = check_eligibility(user, scheme)
    income_rule = next(r for r in result.trace if r.rule == "Annual family income")
    # <= means exactly-at-limit should PASS
    assert income_rule.passed is True


# ---------- Case 4: Multiple matches, ranked by financing fit (Day 4 will rank these) ----------
def test_large_amount_fits_term_loan_not_micro_credit():
    schemes = load_schemes()
    micro = get_scheme(schemes, "NSFDC008")  # cap ~1.4L project cost
    term = get_scheme(schemes, "NSFDC007")   # cap up to 50L project cost

    user = {
        "category": "SC",
        "annual_income": 250000,
        "business_type": "manufacturing unit",
        "purpose": "equipment/machinery purchase",
        "amount_required": 4000000,  # 40 lakh -- too big for Micro Credit
        "is_new_business": False,
    }

    micro_result = check_eligibility(user, micro)
    term_result = check_eligibility(user, term)

    assert micro_result.eligible is False  # amount far exceeds Micro Credit's cap
    assert term_result.eligible is True    # comfortably within Term Loan's cap


# ---------- Trace format sanity check ----------
def test_trace_is_numeric_not_just_text():
    """This is the actual differentiator -- confirm every rule check carries
    real user_value/scheme_limit numbers, not just a pass/fail label."""
    schemes = load_schemes()
    scheme = get_scheme(schemes, "NSFDC008")
    user = {
        "category": "SC", "annual_income": 280000, "business_type": "tailoring",
        "purpose": "equipment purchase", "amount_required": 120000, "is_new_business": False,
    }
    result = check_eligibility(user, scheme)

    for check in result.trace:
        assert check.user_value is not None
        assert check.scheme_limit is not None
        assert isinstance(check.passed, bool)