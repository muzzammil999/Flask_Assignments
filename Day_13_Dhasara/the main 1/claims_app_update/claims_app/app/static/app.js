// Convenience only: the server validates and authorizes everything again.
document.addEventListener("DOMContentLoaded", () => {
  const policy = document.getElementById("policy_id"), member = document.getElementById("member_id");
  if (policy && member && policy.tagName === "SELECT") {
    /**
   * Show only the members that belong to the chosen policy.
   * Why: fewer wrong picks; server validate_claim still enforces member/policy match. Runs on load and on policy change.
   */
    const filter = () => [...member.options].forEach(o => {
      o.hidden = o.dataset.policy && o.dataset.policy !== policy.value;
      if (o.hidden && o.selected) member.value = "";
    });
    policy.addEventListener("change", filter);
    filter();
  }
  /**
   * Ask before destructive buttons such as Reject.
   * Why: stops accidental irreversible decisions; the routes_claims reject action is still guarded server side.
   */
  document.querySelectorAll("[data-confirm]").forEach(b =>
    b.addEventListener("click", e => { if (!confirm(b.dataset.confirm)) e.preventDefault(); }));
});

// Live payout preview on the officer's approval form (display only; the server recomputes with Decimal).
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("approve-form");
  if (!form) return;
  const ded = parseFloat(form.dataset.ded), copay = parseFloat(form.dataset.copay);
  const input = document.getElementById("eligible_amount");
  const fmt = n => "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  /**
   * Recompute deduction and payout whenever the eligible amount changes.
   * Why: preview of services.compute_payout for the officer; display only, server recomputes with Decimal.
   */
  input.addEventListener("input", () => {
    const e = parseFloat(input.value);
    if (isNaN(e) || e <= 0) { document.getElementById("pv-copay").textContent = "-"; document.getElementById("pv-payout").textContent = "-"; return; }
    const base = e - Math.min(e, ded);
    document.getElementById("pv-copay").textContent = "-" + fmt(base * copay / 100);
    document.getElementById("pv-payout").textContent = fmt(base * (1 - copay / 100));
  });
});
