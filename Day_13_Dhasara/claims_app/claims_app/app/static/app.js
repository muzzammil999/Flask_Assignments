// Convenience only: the server validates and authorizes everything again.
document.addEventListener("DOMContentLoaded", () => {
  const policy = document.getElementById("policy_id"), member = document.getElementById("member_id");
  if (policy && member && policy.tagName === "SELECT") {
    /** Show only the members that belong to the chosen policy. */
    const filter = () => [...member.options].forEach(o => {
      o.hidden = o.dataset.policy && o.dataset.policy !== policy.value;
      if (o.hidden && o.selected) member.value = "";
    });
    policy.addEventListener("change", filter);
    filter();
  }
  /** Ask before destructive buttons such as Reject. */
  document.querySelectorAll("[data-confirm]").forEach(b =>
    b.addEventListener("click", e => { if (!confirm(b.dataset.confirm)) e.preventDefault(); }));
});
