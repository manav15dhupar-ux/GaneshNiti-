"""
matching_engine.py — Day 4, second deliverable.

WHAT THIS DOES:
Takes eligibility results (from eligibility_engine.py) and scores/ranks them
by FINANCING FIT -- how well the loan amount and purpose actually suit the
user's need -- rather than generic profile similarity. This is deliberate:
myScheme ranks by broad profile match, we rank by whether this specific
financing product is the RIGHT SIZE and RIGHT PURPOSE for what the user
actually asked for.

SCORING WEIGHTS (documented so this is explainable, not a black box):
- Eligibility (must be True to score at all): gatekeeper, not a scored factor
- Amount fit (40 points): how well the requested amount fits within the
  scheme's cap -- a request that uses most of the available room scores
  higher than one that barely uses a fraction of a much larger scheme's cap
  (e.g. someone needing 1.2L should rank Micro Credit Finance, cap 1.4L,
  above Term Loan, cap 50L, even though both could technically cover it)
- Purpose match (30 points): exact/close match on stated purpose vs.
  scheme's supported purposes
- Category match strength (20 points): exact category match
- Business stage match (10 points): new/existing business alignment

This is intentionally simple and fully explainable -- every point is
traceable to a specific comparison, not a trained/opaque score.

HOW TO TEST:
    pytest tests/test_matching_engine.py -v
"""

from dataclasses import dataclass, field
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from eligibility_engine import EligibilityResult


@dataclass
class MatchResult:
    scheme_id: str
    scheme_name: str
    eligible: bool
    match_score: int  # 0-100, only meaningful when eligible=True
    score_breakdown: dict
    trace: list


def _amount_fit_score(user_amount: Optional[float], scheme: dict) -> int:
    """Scores how well the requested amount fits the scheme's actual capacity.
    A tight fit (using most of the scheme's room) scores higher than a loose
    fit (using a tiny fraction of a much bigger scheme's cap) -- this is what
    makes a 1.2L request rank Micro Credit Finance above Term Loan, even
    though Term Loan could technically also cover it."""
    cap = scheme.get("maximumProjectCost") or scheme.get("maximumLoanAmount")
    if cap is None or user_amount is None or user_amount <= 0:
        return 20  # neutral score when we can't compare meaningfully
    if user_amount > cap:
        return 0  # shouldn't happen if eligibility already failed on this, but safe default
    utilization = user_amount / cap
    # Reward requests that use a meaningful portion of the scheme's capacity;
    # a request using <5% of a much larger scheme's cap suggests a smaller
    # scheme would fit better.
    if utilization >= 0.5:
        return 40
    elif utilization >= 0.2:
        return 32
    elif utilization >= 0.05:
        return 22
    else:
        return 10


def _purpose_match_score(user_purpose: Optional[str], scheme: dict) -> int:
    supported = scheme.get("supportedPurposes") or []
    if not user_purpose or not supported:
        return 15  # neutral when we can't compare
    stopwords = {"and", "for", "the", "a", "an", "of", "to", "or", "purchase", "setup"}

    def keywords(text):
        cleaned = text.lower().replace("/", " ").replace(",", " ")
        return {w for w in cleaned.split() if w not in stopwords and len(w) > 2}

    user_words = keywords(user_purpose)
    matches = sum(1 for p in supported if user_words & keywords(p))
    return 30 if matches > 0 else 5


def _category_match_score(user_category: Optional[str], scheme: dict) -> int:
    target_groups = scheme.get("targetGroups") or []
    if not user_category:
        return 0
    exact = any(user_category.strip().lower() == tg.strip().lower() for tg in target_groups)
    return 20 if exact else 10


def _business_stage_score(is_new: Optional[bool], scheme: dict) -> int:
    if is_new is None:
        return 5
    if is_new:
        return 10 if scheme.get("newBusinessAllowed") else 0
    return 10 if scheme.get("existingBusinessAllowed") else 0


def calculate_match_score(user_profile: dict, scheme: dict, eligibility_result: EligibilityResult) -> MatchResult:
    if not eligibility_result.eligible:
        return MatchResult(
            scheme_id=scheme.get("schemeId"),
            scheme_name=scheme.get("schemeName"),
            eligible=False,
            match_score=0,
            score_breakdown={},
            trace=eligibility_result.trace,
        )

    breakdown = {
        "amount_fit": _amount_fit_score(user_profile.get("amount_required"), scheme),
        "purpose_match": _purpose_match_score(user_profile.get("purpose") or user_profile.get("business_type"), scheme),
        "category_match": _category_match_score(user_profile.get("category"), scheme),
        "business_stage": _business_stage_score(user_profile.get("is_new_business"), scheme),
    }
    total = sum(breakdown.values())

    return MatchResult(
        scheme_id=scheme.get("schemeId"),
        scheme_name=scheme.get("schemeName"),
        eligible=True,
        match_score=total,
        score_breakdown=breakdown,
        trace=eligibility_result.trace,
    )


def rank_schemes(user_profile: dict, schemes: list, eligibility_results: list) -> list:
    """Takes the full list of eligibility results (eligible AND ineligible)
    and returns MatchResults sorted by score descending. Ineligible schemes
    are included at the end (score 0) so the frontend can still show WHY
    they didn't match, not just hide them."""
    scheme_lookup = {s["schemeId"]: s for s in schemes}
    results = [
        calculate_match_score(user_profile, scheme_lookup[er.scheme_id], er)
        for er in eligibility_results
        if er.scheme_id in scheme_lookup
    ]
    return sorted(results, key=lambda r: r.match_score, reverse=True)