// app.js — form submission + results rendering for GaneshNiti.
// Results always come from the real backend (POST /recommend); nothing here is mocked.

// Same origin by default. When the page is opened straight from disk (file://),
// fall back to a locally running backend.
const API_BASE =
  window.GANESHNITI_API_BASE ||
  (window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "");

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

// Only ever link to http(s) URLs coming from data.
function safeUrl(url) {
  return typeof url === "string" && /^https?:\/\//i.test(url) ? url : null;
}

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

  // The numeric trace IS the differentiator: show every rule checked, not just yes/no.
  const traceRows = (scheme.trace || []).map(t => {
    const icon = t.passed ? "&#10003;" : "&#10007;";
    const detail = t.detail ? ` (${escapeHtml(t.detail)})` : "";
    return `<li>${icon} <strong>${escapeHtml(t.rule)}:</strong> ${escapeHtml(t.userValue)} vs ${escapeHtml(t.schemeLimit)}${detail}</li>`;
  }).join("");

  const repaymentBlock = scheme.repayment
    ? `<p class="mb-1"><strong>Quarterly repayment:</strong> &#8377;${Number(scheme.repayment.quarterlyInstallment).toLocaleString("en-IN")}
       (${escapeHtml(scheme.repayment.numInstallments)} installments at ${escapeHtml(scheme.repayment.annualInterestRate)}% p.a.)</p>`
    : "";

  const partnersBlock = (scheme.suggestedPartners && scheme.suggestedPartners.length)
    ? `<p class="mb-1 mt-2"><strong>Suggested Channel Partner</strong> <span class="simulated-note">simulated data</span></p>
       <ul>${scheme.suggestedPartners.map(p => `<li>${escapeHtml(p.partnerName)} (${escapeHtml(p.partnerType)}, ${escapeHtml(p.district || p.state)})</li>`).join("")}</ul>`
    : "";

  const docs = (scheme.requiredDocuments || []);
  const docsBlock = scheme.eligible && docs.length
    ? `<details class="mt-2"><summary>Documents to keep ready (${docs.length})</summary>
         <ul style="font-size:0.85rem;">${docs.map(d => `<li>${escapeHtml(d)}</li>`).join("")}</ul></details>`
    : "";

  const src = safeUrl(scheme.officialSourceUrl);
  const sourceBlock = src
    ? `<p class="mt-2 mb-0" style="font-size:0.8rem;"><a href="${escapeHtml(src)}" target="_blank" rel="noopener noreferrer">Official source</a>${
        scheme.lastVerified ? ` &middot; verified ${escapeHtml(scheme.lastVerified)}` : ""}</p>`
    : "";

  return `
    <div class="col-md-6 col-lg-4">
      <div class="scheme-card">
        <div class="d-flex justify-content-between align-items-start mb-2">
          <h5>${escapeHtml(scheme.schemeName)}</h5>
          <span class="match-score">${escapeHtml(scheme.matchScore)}</span>
        </div>
        ${badge}
        <ul class="mt-3" style="font-size:0.85rem;">${traceRows}</ul>
        ${repaymentBlock}
        ${partnersBlock}
        ${docsBlock}
        ${sourceBlock}
      </div>
    </div>
  `;
}

// Profile form: collect fields + free text, call the backend, hand the response
// to results.html via sessionStorage (survives the redirect, cleared with the tab).
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("profile-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const button = form.querySelector("button[type=submit]");
    const originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = "Finding schemes...";

    const isNew = document.getElementById("isNewBusiness").value;
    const payload = {
      category: document.getElementById("category").value,
      state: document.getElementById("state").value.trim(),
      annualIncome: Number(document.getElementById("income").value) || null,
      businessType: document.getElementById("businessType").value.trim(),
      amountRequired: Number(document.getElementById("amount").value) || null,
      isNewBusiness: isNew === "" ? null : isNew === "true",
      requirement: document.getElementById("requirement").value,
    };

    try {
      const response = await fetch(`${API_BASE}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(`Backend returned ${response.status}`);

      const data = await response.json();
      sessionStorage.setItem("recommendResults", JSON.stringify(data.results));
      window.location.href = "results.html";
    } catch (err) {
      console.error("Failed to get recommendation:", err);
      alert("Couldn't reach the server. If you are running locally, start it with: uvicorn main:app --reload (inside backend/)");
      button.disabled = false;
      button.textContent = originalLabel;
    }
  });
});
