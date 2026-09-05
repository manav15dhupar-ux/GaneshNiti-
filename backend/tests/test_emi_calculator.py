"""
test_emi_calculator.py — tests the quarterly repayment calculator against
real scheme data, including one HAND-CALCULATED example to independently
verify the formula, not just that the code runs without crashing.

Run with:
    pytest tests/test_emi_calculator.py -v
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.emi_calculator import calculate_quarterly_repayment, _parse_interest_rate, _parse_years_from_text, _parse_months_from_text

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "schemes_preview.json"


def load_schemes():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_scheme(schemes, scheme_id):
    return next(s for s in schemes if s["schemeId"] == scheme_id)


# ---------- Parsing helper tests ----------
def test_parse_interest_rate_takes_beneficiary_rate():
    # "NSFDC charges 2.5% p.a. to the Channelising Agency, which in turn
    # charges 6.5% p.a. to the beneficiary" -- should extract 6.5, not 2.5
    text = "NSFDC charges 2.5% p.a. to the Channelising Agency, which in turn charges 6.5% p.a. to the beneficiary"
    assert _parse_interest_rate(text) == 6.5


def test_parse_years():
    assert _parse_years_from_text("Up to 7 years (quarterly instalments)") == 7.0
    assert _parse_years_from_text("Up to 3 years (quarterly instalments)") == 3.0


def test_parse_months():
    assert _parse_months_from_text("3 months") == 3.0
    assert _parse_months_from_text("6 months (12 months for plantation/construction activities)") == 6.0


# ---------- Hand-calculated verification (NSFDC Micro Credit Finance demo case) ----------
def test_hand_calculated_micro_credit_example():
    """
    Hand calculation for verification:
    Principal = 120,000 | Annual rate = 6.5% | Total tenure = 3 years (36 months)
    Moratorium = 3 months | Repayment period = 33 months -> 11 quarterly installments
    Quarterly rate = 6.5% / 4 / 100 = 0.01625

    Installment = P * r * (1+r)^n / ((1+r)^n - 1)
                = 120000 * 0.01625 * (1.01625)^11 / ((1.01625)^11 - 1)
    (1.01625)^11 ~= 1.19399
    Installment ~= 120000 * 0.01625 * 1.19399 / 0.19399 ~= 12,002 (approx)
    """
    schemes = load_schemes()
    scheme = get_scheme(schemes, "NSFDC008")  # Micro Credit Finance Scheme

    result = calculate_quarterly_repayment(principal=120000, scheme=scheme)

    assert result.num_installments == 11
    assert result.moratorium_months == 3
    assert result.annual_interest_rate == 6.5
    # allow a small tolerance for manual rounding in the hand-calc above
    assert 11900 <= result.quarterly_installment <= 12100
    assert result.total_interest > 0
    assert abs(result.total_repayment - (result.quarterly_installment * result.num_installments)) < 0.5


def test_term_loan_repayment():
    schemes = load_schemes()
    scheme = get_scheme(schemes, "NSFDC007")  # Term Loan, 8% beneficiary rate, 7 years, 6-month moratorium

    result = calculate_quarterly_repayment(principal=1000000, scheme=scheme)

    assert result.annual_interest_rate == 8.0
    # 7 years = 84 months, minus 6-month moratorium = 78 months -> 26 quarters
    assert result.num_installments == 26
    assert result.quarterly_installment > 0


def test_zero_interest_edge_case():
    """Confirms the calculator doesn't divide by zero if a scheme somehow had 0% interest."""
    fake_scheme = {"interestRate": "0%", "repaymentPeriod": "Up to 2 years", "moratoriumPeriod": "0 months"}
    result = calculate_quarterly_repayment(principal=100000, scheme=fake_scheme)
    assert result.quarterly_installment == 100000 / 8  # 2 years = 8 quarters, no interest


def test_missing_data_uses_documented_fallback():
    """If scheme text can't be parsed, the calculator should still return a
    number (with a note explaining the fallback) rather than crashing."""
    fake_scheme = {"interestRate": "", "repaymentPeriod": "", "moratoriumPeriod": ""}
    result = calculate_quarterly_repayment(principal=50000, scheme=fake_scheme)
    assert result.quarterly_installment > 0
    assert "fallback" in result.notes.lower()