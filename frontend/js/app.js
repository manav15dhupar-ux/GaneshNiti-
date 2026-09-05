// app.js — Day 2 version.
// DUMMY_RESULTS below stands in for what the real backend will return from
// POST /recommend on Day 3+. The shape matches what upload_schemes.py /
// the eligibility engine will actually produce, so swapping in the real
// fetch() call later shouldn't require changing renderResults() at all.

const DUMMY_RESULTS = [
  {
    schemeName: "NSFDC Micro Credit Finance Scheme",
    eligible: true,
    matchScore: 92,
    reasons: [
      "Category matches scheme target group (SC)",
      "Income is within the ₹3,00,000 limit",
      "Project cost is within the ₹1.40 lakh limit",
    ],
    emi: { monthlyEmi: 3805, totalInterest: 12250 },
    requiredDocuments: ["SC caste certificate", "Income certificate", "Identity proof"],
    officialSourceUrl: "https://nsfdc.nic.in/en/micro-credit-finance",
  },
  {
    schemeName: "NSFDC Term Loan Scheme",
    eligible: true,
    matchScore: 78,
    reasons: [
      "Category matches scheme target group (SC)",
      "Income is within the ₹3,00,000 limit",
      "Requested amount is well within the ₹45,00,000 limit",
    ],
    emi: { monthlyEmi: 4980, totalInterest: 46200 },
    requiredDocuments: ["SC caste certificate", "Income certificate", "Project report"],
    officialSourceUrl: "https://nsfdc.nic.in/en/term-loan",
  },
  {
    schemeName: "Stand-Up India Scheme",
    eligible: false,
    matchScore: 21,
    reasons: [
      "This scheme requires a greenfield (brand new) enterprise — an existing business does not qualify",
    ],
    emi: null,
    requiredDocuments: [],
    officialSourceUrl: "https://www.standupmitra.in/",
  },
];

function renderResults(results) {
  const container = document.getElementById("results-list");
  if (!container) return;

  if (!results || results.length === 0) {
    container.innerHTML = `<p class="text-muted">No matching schemes found. Try adjusting your details.</p>`;
    return;
  }

  container.innerHTML = results.map(renderSchemeCard).join("");
}

function renderSchemeCard(scheme) {
  const badge = scheme.eligible
    ? `<span class="badge badge-eligible">Potentially eligible</span>`
    : `<span class="badge badge-ineligible">Not eligible</span>`;

  // The numeric trace IS the differentiator -- show every rule checked,
  // not just a final yes/no.
  const traceRows = (scheme.trace || []).map(t => {
    const icon = t.passed ? "&#10003;" : "&#10007;";
    const detail = t.detail ? ` (${escapeHtml(t.detail)})` : "";
    return `<li>${icon} <strong>${escapeHtml(t.rule)}:</strong> ${escapeHtml(String(t.userValue))} vs ${escapeHtml(String(t.schemeLimit))}${detail}</li>`;
  }).join("");

  const repaymentBlock = scheme.repayment
    ? `<p class="mb-1"><strong>Quarterly repayment:</strong> &#8377;${scheme.repayment.quarterlyInstallment.toLocaleString("en-IN")}
       (${scheme.repayment.numInstallments} installments at ${scheme.repayment.annualInterestRate}% p.a.)</p>`
    : "";

  const partnersBlock = (scheme.suggestedPartners && scheme.suggestedPartners.length)
    ? `<p class="mb-1 mt-2"><strong>Suggested Channel Partner</strong> <span class="simulated-note">simulated data</span></p>
       <ul>${scheme.suggestedPartners.map(p => `<li>${escapeHtml(p.partnerName)} (${escapeHtml(p.partnerType)}, ${escapeHtml(p.district || p.state)})</li>`).join("")}</ul>`
    : "";

  return `
    <div class="col-md-6 col-lg-4">
      <div class="scheme-card">
        <div class="d-flex justify-content-between align-items-start mb-2">
          <h5>${escapeHtml(scheme.schemeName)}</h5>
          <span class="match-score">${scheme.matchScore}</span>
        </div>
        ${badge}
        <ul class="mt-3" style="font-size:0.85rem;">${traceRows}</ul>
        ${repaymentBlock}
        ${partnersBlock}
      </div>
    </div>
  `;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

const API_BASE = "http://127.0.0.1:8000"; // change this if your backend runs elsewhere

// Profile form: collects the real form fields + free text, sends them to
// the real backend, and stores the response so results.html can render it.
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("profile-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      category: document.getElementById("category").value,
      state: document.getElementById("state").value,
      annualIncome: Number(document.getElementById("income").value) || null,
      businessType: document.getElementById("businessType").value,
      amountRequired: Number(document.getElementById("amount").value) || null,
      requirement: document.getElementById("requirement").value,
    };

    try {
      const response = await fetch(`${API_BASE}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }

      const data = await response.json();
      // sessionStorage survives the redirect to results.html but clears
      // when the tab closes -- fine for a demo, no backend session needed.
      sessionStorage.setItem("recommendResults", JSON.stringify(data.results));
      window.location.href = "results.html";
    } catch (err) {
      console.error("Failed to get recommendation:", err);
      alert("Couldn't reach the backend. Is it running? (uvicorn main:app --reload)");
    }
  });
});