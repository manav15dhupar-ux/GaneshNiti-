"""
llm_extraction.py — Day 3 second deliverable (OpenRouter version).

WHAT THIS DOES:
Takes a user's free-text description of their financing need and converts it
into structured fields (category, income, amount, purpose, etc.) using an
LLM API call via OpenRouter (openrouter.ai) -- a single API that gives access
to many different models (OpenAI, Anthropic, Meta, Google, etc.), including
free-tier models, using one API key.

WHAT THIS DOES NOT DO (read this before touching this file):
This file NEVER decides eligibility. It has no scheme data, no rule logic,
no pass/fail decisions. Its only job is turning messy human language into
clean structured data that eligibility_engine.py can then check. If you ever
feel tempted to add "and if income is low, mark them eligible" logic here --
don't. That belongs in eligibility_engine.py, where it can be tested and
audited as a plain, deterministic rule.

WHY THE VALIDATION STEP MATTERS:
LLMs occasionally return malformed JSON, or invent a field that doesn't
belong, or skip a field. This file NEVER trusts the LLM's raw output --
every response is checked against ExtractedProfile below before anything
downstream sees it. If validation fails, we fall back to whatever structured
form fields the user already typed, rather than crashing or guessing.

HOW TO SET THIS UP WITH OPENROUTER
------------------------------------
1. Go to https://openrouter.ai and sign up (free).
2. Go to https://openrouter.ai/keys and create an API key.
3. Set it as an environment variable, never hardcoded:
       export OPENROUTER_API_KEY="your-key-here"
   (On Windows PowerShell: $env:OPENROUTER_API_KEY="your-key-here")
4. Pick a model. OpenRouter hosts many, including free ones (model IDs
   ending in ":free"). Check https://openrouter.ai/models for the current
   list -- free-tier model availability changes over time. This file
   defaults to a small, cheap model that's reliable for structured
   extraction; override it with the OPENROUTER_MODEL environment variable
   if you want to try a different one:
       export OPENROUTER_MODEL="meta-llama/llama-3.1-8b-instruct:free"
5. pip install requests pydantic
   (requests is likely already installed as a FastAPI dependency, but it's
   listed explicitly here since this file uses it directly.)

HOW TO TEST WITHOUT SPENDING API CREDITS
-------------------------------------------
Run this file directly -- it includes a --mock mode that skips the real API
call and returns a fake response, so you can test the validation and
fallback logic for free before wiring in a real key.
    python llm_extraction.py --mock
"""

import json
import os
import sys
from typing import Optional

import requests
from pydantic import BaseModel, ValidationError, field_validator

try:
    from dotenv import load_dotenv
    load_dotenv()  # reads a .env file (if present) and loads its keys as environment variables
except ImportError:
    pass  # dotenv is optional -- if not installed, you can still use `export` manually instead

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "meta-llama/llama-3.1-8b-instruct:free"  # check openrouter.ai/models -- free tier changes over time


class ExtractedProfile(BaseModel):
    """The ONLY shape of data this module is allowed to hand back.
    Anything the LLM returns that doesn't fit this shape gets rejected."""
    category: Optional[str] = None
    state: Optional[str] = None
    annual_income: Optional[float] = None
    business_type: Optional[str] = None
    purpose: Optional[str] = None
    amount_required: Optional[float] = None
    is_new_business: Optional[bool] = None

    @field_validator("annual_income", "amount_required")
    @classmethod
    def must_be_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Amount cannot be negative")
        return v


EXTRACTION_PROMPT = """You are a data extraction tool. You do NOT decide eligibility \
or give financial advice. Your only job is to read the person's description of their \
financing need and pull out structured fields.

Return ONLY a JSON object with these exact keys (use null for anything not mentioned):
{{
  "category": string or null (e.g. "SC", "ST", "OBC", "General"),
  "state": string or null,
  "annual_income": number or null (in rupees, no commas or symbols),
  "business_type": string or null,
  "purpose": string or null (what the money is for, e.g. "equipment purchase"),
  "amount_required": number or null (in rupees, no commas or symbols),
  "is_new_business": boolean or null (true if starting fresh, false if expanding an existing business)
}}

Do not include any text before or after the JSON. Do not invent values that \
weren't stated or clearly implied.

Person's description:
\"\"\"{user_text}\"\"\"
"""


def _mock_llm_call(user_text: str) -> str:
    """Fake LLM response for testing without API credits or a key."""
    return json.dumps({
        "category": "SC",
        "state": "Maharashtra",
        "annual_income": 280000,
        "business_type": "tailoring",
        "purpose": "equipment purchase",
        "amount_required": 120000,
        "is_new_business": False,
    })


def _real_llm_call(user_text: str) -> str:
    """Calls the LLM via OpenRouter's API (OpenAI-compatible REST endpoint).
    Works with any model OpenRouter hosts -- just change OPENROUTER_MODEL."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Set the OPENROUTER_API_KEY environment variable first.")

    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)

    response = requests.post(
        url=OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # These two headers are optional but recommended by OpenRouter --
            # they show up on your OpenRouter dashboard and don't affect billing.
            "HTTP-Referer": "https://github.com/",  # replace with your repo URL if you like
            "X-Title": "PS92 Scheme Navigator",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": EXTRACTION_PROMPT.format(user_text=user_text)}],
            "temperature": 0,  # deterministic-ish output for extraction, not creative writing
        },
        timeout=20,
    )
    response.raise_for_status()  # raises for 4xx/5xx (bad key, rate limit, etc.)
    data = response.json()
    return data["choices"][0]["message"]["content"]


def extract_structured_data(user_text: str, form_fields: Optional[dict] = None, use_mock: bool = False) -> dict:
    """
    Main entry point. Returns a dict matching ExtractedProfile's fields.

    form_fields: whatever the user already typed into the structured form
    (category, state, income, etc.) -- used as a SAFE FALLBACK if the LLM
    call fails or returns something that doesn't validate. This means a
    broken LLM call never crashes the app or blocks a recommendation.
    """
    form_fields = form_fields or {}

    if not user_text or not user_text.strip():
        # No free text given -- just use whatever the structured form provided.
        return form_fields

    try:
        raw_response = _mock_llm_call(user_text) if use_mock else _real_llm_call(user_text)

        # Some models wrap JSON in markdown code fences even when told not to --
        # strip that defensively before parsing.
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        parsed = json.loads(cleaned)
        validated = ExtractedProfile(**parsed)
        result = validated.model_dump(exclude_none=True)
        # Structured form fields fill in anything the LLM didn't catch.
        return {**form_fields, **result}

    except (json.JSONDecodeError, ValidationError, RuntimeError, requests.RequestException, KeyError, IndexError) as e:
        print(f"[llm_extraction] Extraction failed ({e}) -- falling back to structured form fields only.")
        return form_fields


if __name__ == "__main__":
    use_mock = "--mock" in sys.argv
    sample_text = "I run a small tailoring business and want to buy two more sewing machines. I need around 1.2 lakh rupees."

    print(f"Testing extraction ({'MOCK' if use_mock else 'REAL API (OpenRouter)'} mode)...")
    print(f"Input: {sample_text}\n")

    result = extract_structured_data(sample_text, form_fields={"category": "SC", "state": "Maharashtra"}, use_mock=use_mock)
    print("Extracted:")
    print(json.dumps(result, indent=2))