"""
routers/recommend.py — Day 4 final deliverable: the actual /recommend endpoint.

This is where every piece built so far comes together:
    LLM extraction -> eligibility engine (numeric trace) -> matching engine
    (financing-fit ranking) -> EMI calculator (top match only) -> JSON response

Nothing new is invented here -- this file just calls, in order, the pieces
your team already built and tested individually.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from services.firestore_client import get_all_schemes, get_all_channel_partners
from services.llm_extraction import extract_structured_data
from services.eligibility_engine import check_all_schemes
from services.matching_engine import rank_schemes
from services.emi_calculator import calculate_quarterly_repayment
from services.partner_locator import find_matching_partners, format_partner_summary

router = APIRouter()


class RecommendRequest(BaseModel):
    category: Optional[str] = None
    state: Optional[str] = None
    annualIncome: Optional[float] = None
    businessType: Optional[str] = None
    amountRequired: Optional[float] = None
    isNewBusiness: Optional[bool] = None
    requirement: Optional[str] = None  # the free-text description


@router.post("/recommend")
def recommend(request: RecommendRequest):
    # Step 1: whatever the user already typed into the structured form
    form_fields = {
        "category": request.category,
        "state": request.state,
        "annual_income": request.annualIncome,
        "business_type": request.businessType,
        "amount_required": request.amountRequired,
        "is_new_business": request.isNewBusiness,
    }
    form_fields = {k: v for k, v in form_fields.items() if v is not None}

    # Step 2: LLM extraction fills in/confirms fields from the free text,
    # with a safe fallback to form_fields if it fails for any reason.
    user_profile = extract_structured_data(request.requirement or "", form_fields=form_fields, use_mock=False)

    # Step 3: verified scheme data (Firestore, with local-JSON fallback built in)
    schemes = get_all_schemes()

    # Step 4: deterministic eligibility check, one numeric trace per scheme
    eligibility_results = check_all_schemes(user_profile, schemes)

    # Step 5: rank by financing fit (eligible schemes first, best fit highest)
    ranked = rank_schemes(user_profile, schemes, eligibility_results)

    # Step 6: EMI/quarterly repayment for the top eligible match only
    # (calculating this for every scheme isn't useful -- only the
    # recommendation the user will actually act on needs a real number)
    scheme_lookup = {s["schemeId"]: s for s in schemes}
    top_eligible = next((r for r in ranked if r.eligible), None)
    repayment = None
    if top_eligible and user_profile.get("amount_required"):
        repayment = calculate_quarterly_repayment(
            principal=user_profile["amount_required"],
            scheme=scheme_lookup[top_eligible.scheme_id],
        )

    # Step 7: assemble the response
    results = []
    for r in ranked:
        entry = {
            "schemeId": r.scheme_id,
            "schemeName": r.scheme_name,
            "eligible": r.eligible,
            "matchScore": r.match_score,
            "scoreBreakdown": r.score_breakdown,
            "trace": [
                {
                    "rule": t.rule,
                    "userValue": t.user_value,
                    "schemeLimit": t.scheme_limit,
                    "passed": t.passed,
                    "detail": t.detail,
                }
                for t in r.trace
            ],
            "suggestedPartners": []  # Default to empty for non-top schemes
        }

        # Inject repayment AND channel partners ONLY for the top eligible recommendation
        if top_eligible and r.scheme_id == top_eligible.scheme_id:
            if repayment:
                entry["repayment"] = {
                    "quarterlyInstallment": repayment.quarterly_installment,
                    "numInstallments": repayment.num_installments,
                    "totalInterest": repayment.total_interest,
                    "annualInterestRate": repayment.annual_interest_rate,
                    "notes": repayment.notes,
                }
            
            # Moved inside the block to honor the requirement
            partners = get_all_channel_partners()
            matches = find_matching_partners(r.scheme_name, user_profile.get("state"), partners)
            entry["suggestedPartners"] = [format_partner_summary(p) for p in matches]

        results.append(entry)

    return {
        "extractedProfile": user_profile,
        "results": results,
    }
