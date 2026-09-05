"""
eligibility_engine.py — Day 3 core deliverable.

WHAT CHANGED FROM THE ORIGINAL PLAN:
This does NOT just return eligible=True/False with text reasons. It returns a
NUMERIC TRACE for every rule checked: the user's actual value, the scheme's
actual limit, and a pass/fail verdict. This is your #1 differentiator against
myScheme's Yes/No eligibility questionnaire — a judge (or the user) can see
exactly *how close* someone is to qualifying, not just a final verdict.

THE GOLDEN RULE THIS FILE ENFORCES:
The LLM never touches this file. Every decision here is a plain Python
comparison against numbers that come straight from your verified spreadsheet.
If a judge asks "how do you know this isn't the AI making things up," the
answer is: this file. Show them this file.

HOW TO TEST:
    pytest tests/test_eligibility.py -v
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RuleCheck:
    """One line of the numeric trace — one rule, one verdict."""
    rule: str            # human-readable name, e.g. "Annual family income"
    user_value: str       # what the user has, e.g. "₹2,80,000"
    scheme_limit: str     # what the scheme requires, e.g. "≤ ₹3,00,000"
    passed: bool
    detail: Optional[str] = None  # extra context, e.g. "₹20,000 under the limit"
    is_gate: bool = True  # if False, shown for transparency but does NOT block
                           # overall eligibility -- used for inherently soft/
                           # subjective checks like purpose matching, where
                           # free-text descriptions rarely match official
                           # scheme wording exactly. Purpose fit still affects
                           # RANKING via matching_engine.py's scoring.


@dataclass
class EligibilityResult:
    scheme_id: str
    scheme_name: str
    eligible: bool
    trace: list = field(default_factory=list)  # list[RuleCheck]

    def reasons_as_text(self):
        """Fallback plain-English summary, for places that don't render the full trace table."""
        return [
            f"{r.rule}: {r.user_value} vs {r.scheme_limit} -> {'PASS' if r.passed else 'FAIL'}"
            for r in self.trace
        ]


def _format_currency(value):
    if value is None:
        return "not specified"
    return f"\u20b9{value:,.0f}"


def check_eligibility(user_profile: dict, scheme: dict) -> EligibilityResult:
    """
    user_profile expected keys (all from structured LLM extraction, already
    validated -- this function does NOT call the LLM and does NOT trust
    unvalidated free text):
        category: str            e.g. "SC"
        annual_income: float
        business_type: str        e.g. "tailoring"
        purpose: str               e.g. "equipment purchase"
        amount_required: float
        is_new_business: bool

    scheme expected keys (from Firestore, matching upload_schemes.py's schema):
        schemeId, schemeName, targetGroups (list), incomeLimit (number|None),
        maximumProjectCost (number|None), maximumLoanAmount (number|None),
        supportedPurposes (list), newBusinessAllowed (bool),
        existingBusinessAllowed (bool)
    """
    trace = []

    # --- Rule 1: Category / target group match ---
    target_groups = scheme.get("targetGroups") or []
    user_category = (user_profile.get("category") or "").strip().lower()
    # Word-boundary match, NOT substring match -- a naive substring check
    # would incorrectly match "SC" against "ST (Scheduled Tribes)", since
    # "sc" is literally contained inside the word "Scheduled". Caught by
    # a Day 4 matching-engine test that surfaced an SC user ranking against
    # an ST-only scheme.
    def _category_tokens(text):
        return set(re.findall(r"[a-z]+", text.lower()))
    category_match = any(user_category in _category_tokens(tg) for tg in target_groups) if user_category else False
    trace.append(RuleCheck(
        rule="Category",
        user_value=user_profile.get("category", "not provided"),
        scheme_limit=" / ".join(target_groups) if target_groups else "any category",
        passed=category_match,
    ))

    # --- Rule 2: Income limit ---
    income_limit = scheme.get("incomeLimit")
    user_income = user_profile.get("annual_income")
    if income_limit is None:
        # Scheme has no numeric income cap (stored as null with a ...Raw text field) -- treat as no limit.
        income_ok = True
        income_check = RuleCheck(
            rule="Annual family income",
            user_value=_format_currency(user_income),
            scheme_limit="no numeric limit stated",
            passed=True,
            detail=scheme.get("incomeLimitRaw"),
        )
    elif user_income is None:
        income_ok = False
        income_check = RuleCheck(
            rule="Annual family income",
            user_value="not provided",
            scheme_limit=f"\u2264 {_format_currency(income_limit)}",
            passed=False,
        )
    else:
        income_ok = user_income <= income_limit
        margin = income_limit - user_income
        income_check = RuleCheck(
            rule="Annual family income",
            user_value=_format_currency(user_income),
            scheme_limit=f"\u2264 {_format_currency(income_limit)}",
            passed=income_ok,
            detail=(f"{_format_currency(abs(margin))} {'under' if margin >= 0 else 'over'} the limit"),
        )
    trace.append(income_check)

    # --- Rule 3: Project cost / amount required within scheme's maximum ---
    max_project_cost = scheme.get("maximumProjectCost")
    max_loan = scheme.get("maximumLoanAmount")
    amount_cap = max_project_cost if max_project_cost is not None else max_loan
    user_amount = user_profile.get("amount_required")

    if amount_cap is None:
        amount_ok = True
        amount_check = RuleCheck(
            rule="Amount required",
            user_value=_format_currency(user_amount),
            scheme_limit="no numeric cap stated",
            passed=True,
        )
    elif user_amount is None:
        amount_ok = False
        amount_check = RuleCheck(
            rule="Amount required",
            user_value="not provided",
            scheme_limit=f"\u2264 {_format_currency(amount_cap)}",
            passed=False,
        )
    else:
        amount_ok = user_amount <= amount_cap
        margin = amount_cap - user_amount
        amount_check = RuleCheck(
            rule="Amount required",
            user_value=_format_currency(user_amount),
            scheme_limit=f"\u2264 {_format_currency(amount_cap)}",
            passed=amount_ok,
            detail=(f"{_format_currency(abs(margin))} {'under' if margin >= 0 else 'over'} the cap"),
        )
    trace.append(amount_check)

    # --- Rule 4: New vs existing business ---
    is_new = user_profile.get("is_new_business")
    if is_new is None:
        business_stage_ok = True  # unknown -- don't fail the user for a field we don't have yet
        stage_check = RuleCheck(
            rule="Business stage",
            user_value="not provided",
            scheme_limit="new: {} / existing: {}".format(
                scheme.get("newBusinessAllowed"), scheme.get("existingBusinessAllowed")),
            passed=True,
        )
    elif is_new:
        business_stage_ok = bool(scheme.get("newBusinessAllowed"))
        stage_check = RuleCheck(
            rule="Business stage",
            user_value="new business",
            scheme_limit="new business allowed" if scheme.get("newBusinessAllowed") else "new business NOT allowed",
            passed=business_stage_ok,
        )
    else:
        business_stage_ok = bool(scheme.get("existingBusinessAllowed"))
        stage_check = RuleCheck(
            rule="Business stage",
            user_value="existing business",
            scheme_limit="existing business allowed" if scheme.get("existingBusinessAllowed") else "existing business NOT allowed",
            passed=business_stage_ok,
        )
    trace.append(stage_check)

    # --- Rule 5: Purpose match (word-overlap check, not whole-phrase containment) ---
    # Your scheme data has long, descriptive purpose text (e.g. "equipment/stock
    # purchase"), so a user typing "equipment purchase" should still match --
    # whole-phrase "contains" checks are too strict for real free-text input.
    _STOPWORDS = {"and", "for", "the", "a", "an", "of", "to", "or", "purchase", "setup"}

    def _keywords(text):
        cleaned = text.lower().replace("/", " ").replace(",", " ")
        return {w for w in cleaned.split() if w not in _STOPWORDS and len(w) > 2}

    supported_purposes = scheme.get("supportedPurposes") or []
    user_purpose = (user_profile.get("purpose") or user_profile.get("business_type") or "").strip().lower()
    purpose_match = True  # default true (don't punish missing data) unless we can actually check
    if user_purpose and supported_purposes:
        user_words = _keywords(user_purpose)
        purpose_match = any(
            user_words & _keywords(p)  # any shared meaningful word counts as a match
            for p in supported_purposes
        )
    trace.append(RuleCheck(
        rule="Purpose match",
        user_value=user_profile.get("purpose") or user_profile.get("business_type") or "not provided",
        scheme_limit=", ".join(supported_purposes) if supported_purposes else "any purpose",
        passed=purpose_match,
        is_gate=False,  # soft signal only -- see RuleCheck.is_gate docstring above
    ))

    overall_eligible = all(check.passed for check in trace if check.is_gate)

    return EligibilityResult(
        scheme_id=scheme.get("schemeId"),
        scheme_name=scheme.get("schemeName"),
        eligible=overall_eligible,
        trace=trace,
    )


def check_all_schemes(user_profile: dict, schemes: list) -> list:
    """Runs check_eligibility against every scheme and returns all results
    (both eligible and ineligible -- the matching engine decides what to show)."""
    return [check_eligibility(user_profile, scheme) for scheme in schemes]