"""
emi_calculator.py — Day 4, first deliverable.

WHAT THIS DOES:
Calculates the QUARTERLY installment for a loan -- not a monthly EMI. This
matters because NSFDC structures repayment in quarterly installments across
all three schemes (Micro Credit Finance, Term Loan, Educational Loan), a
correction made after cross-checking against NSFDC's official policy
documentation. A standard "monthly EMI calculator" would give the wrong
number here, even if the math itself were correct.

ASSUMPTIONS (stated explicitly, since these matter for accuracy):
- The moratorium period is INCLUDED within the total repayment tenure (e.g.
  "up to 7 years including moratorium"), not additional to it -- this
  matches how NSFDC describes tenure in its scheme documentation.
- No interest is assumed to accrue/capitalize during the moratorium period
  (a simplification -- NSFDC's exact moratorium interest treatment isn't
  detailed in public documentation at the level needed to model it more
  precisely). This should be flagged to judges as a stated assumption, not
  hidden as if it were an exact bank calculation.
- Uses the standard loan amortization formula, adapted for quarterly
  (not monthly) compounding periods.

HOW TO TEST:
    pytest tests/test_emi_calculator.py -v
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class RepaymentResult:
    quarterly_installment: float
    num_installments: int
    total_repayment: float
    total_interest: float
    principal: float
    annual_interest_rate: float
    moratorium_months: int
    repayment_months: int
    notes: str = ""


def _parse_years_from_text(text: str) -> Optional[float]:
    """Extracts a number of years from free text like 'Up to 7 years
    (quarterly instalments)' or 'up to 10 years (loans up to Rs.10 lakh)'."""
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*year", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def _parse_months_from_text(text: str) -> Optional[float]:
    """Extracts a number of months from free text like '6 months (12 months
    for plantation/construction activities)' -- takes the FIRST number found,
    since that's the general-case figure; special-case figures in parentheses
    are intentionally not auto-selected (a human should review those cases)."""
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*month", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def _parse_interest_rate(text: str) -> Optional[float]:
    """Extracts the BENEFICIARY interest rate (the rate charged to the user,
    not the rate NSFDC charges the Channelising Agency). Looks for the LAST
    percentage in the text, since our data consistently writes rates as
    'NSFDC charges X% to SCA, which charges Y% to beneficiary' -- Y is what
    the user actually pays."""
    if not text:
        return None
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", text)
    if matches:
        return float(matches[-1])
    return None


def calculate_quarterly_repayment(principal: float, scheme: dict) -> RepaymentResult:
    """
    principal: the loan amount (should already be within the scheme's max
    loan amount -- this function does not check eligibility, only computes
    repayment figures for an amount the eligibility engine has already
    approved).

    scheme: a Firestore scheme document (same shape as eligibility_engine.py
    expects) -- reads interestRate, repaymentPeriod, moratoriumPeriod as text
    fields and parses the numbers out of them.
    """
    annual_rate = _parse_interest_rate(scheme.get("interestRate", ""))
    total_years = _parse_years_from_text(scheme.get("repaymentPeriod", ""))
    moratorium_months = _parse_months_from_text(scheme.get("moratoriumPeriod", "")) or 0

    notes = []
    if annual_rate is None:
        annual_rate = 8.0  # conservative fallback -- should not normally happen with verified data
        notes.append("Interest rate could not be parsed from scheme text; used 8% fallback -- verify manually.")
    if total_years is None:
        total_years = 5.0
        notes.append("Repayment period could not be parsed from scheme text; used 5-year fallback -- verify manually.")

    total_months = total_years * 12
    repayment_months = max(total_months - moratorium_months, 3)  # at least one quarter to repay over
    num_installments = max(int(repayment_months // 3), 1)

    quarterly_rate = (annual_rate / 100) / 4

    if quarterly_rate == 0:
        quarterly_installment = principal / num_installments
    else:
        factor = (1 + quarterly_rate) ** num_installments
        quarterly_installment = principal * quarterly_rate * factor / (factor - 1)

    total_repayment = quarterly_installment * num_installments
    total_interest = total_repayment - principal

    return RepaymentResult(
        quarterly_installment=round(quarterly_installment, 2),
        num_installments=num_installments,
        total_repayment=round(total_repayment, 2),
        total_interest=round(total_interest, 2),
        principal=principal,
        annual_interest_rate=annual_rate,
        moratorium_months=int(moratorium_months),
        repayment_months=int(repayment_months),
        notes="; ".join(notes) if notes else "Calculated from scheme data; assumes no interest accrual during moratorium.",
    )