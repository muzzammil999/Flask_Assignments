/*
 * app.js - the small JavaScript helpers of the Claims Simulator.
 *
 * IMPORTANT: this file is for CONVENIENCE only (live hints, hiding things, confirm
 * boxes). Nothing here is security. The Flask server (app.py) checks every value
 * again, so a user who turns JavaScript off or edits the page gains nothing.
 *
 * How it works: when the page has finished loading, setupPage() looks for the
 * special elements each helper needs. If an element is not on the current page the
 * helper simply does nothing, so ONE file can serve all pages.
 *
 * Features:
 *   1. showOnlyMembersOfPolicy()  - claim form: member list follows the chosen policy
 *   2. askBeforeClicking()        - "Are you sure?" box on dangerous buttons
 *   3. showPayoutPreview()        - approve form: live payout calculation
 *   4. setupShowPassword()        - "Show password" checkboxes
 *   5. setupPasswordHints()       - change-password page: strength + match hints
 */


// ---------------------------------------------------------------------------
// 1. Claim form: show only the members that belong to the chosen policy
// ---------------------------------------------------------------------------
function showOnlyMembersOfPolicy() {
  var policyBox = document.getElementById("policy_id");
  var memberBox = document.getElementById("member_id");

  // This helper only works when BOTH boxes exist and the policy box is a drop-down list.
  // (A hospital desk types the policy id into a text box, so nothing happens for them.)
  if (!policyBox || !memberBox || policyBox.tagName !== "SELECT") {
    return;
  }

  /** Hide every member option that belongs to a different policy than the selected one. */
  function filterMembers() {
    var options = memberBox.options;
    for (var i = 0; i < options.length; i++) {
      var option = options[i];
      // Each <option> has data-policy="101" in the HTML. The empty first option has none.
      var belongsToOtherPolicy = option.dataset.policy && option.dataset.policy !== policyBox.value;
      option.hidden = Boolean(belongsToOtherPolicy);

      // If the hidden option was selected, clear the choice so a wrong member is not sent.
      if (option.hidden && option.selected) {
        memberBox.value = "";
      }
    }
  }

  policyBox.addEventListener("change", filterMembers);   // run again whenever the policy changes
  filterMembers();                                       // and once now, for the starting value
}


// ---------------------------------------------------------------------------
// 2. "Are you sure?" box on buttons such as Reject
// ---------------------------------------------------------------------------
/** For every element with data-confirm="text", ask the question before the click goes through. */
function askBeforeClicking() {
  var buttons = document.querySelectorAll("[data-confirm]");
  buttons.forEach(function (button) {
    button.addEventListener("click", function (event) {
      var answeredYes = confirm(button.dataset.confirm);
      if (!answeredYes) {
        event.preventDefault();     // cancel the click, so the form is not sent
      }
    });
  });
}


// ---------------------------------------------------------------------------
// 3. Approve form: live payout preview
// ---------------------------------------------------------------------------
/** Turn a number into rupees with Indian digit grouping, e.g. 1234567.5 -> "₹12,34,567.50". */
function formatRupees(number) {
  return "₹" + number.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * While the officer types the eligible amount, show the co-pay and the payout.
 * It uses the same formula as the server:
 *     payout = (eligible - min(eligible, deductible)) x (1 - copay / 100)
 * This is only a PREVIEW. The server calculates the real payout again with Decimal.
 */
function showPayoutPreview() {
  var form = document.getElementById("approve-form");
  if (!form) {
    return;     // not the claim page of an officer who can approve
  }
  // The server wrote the plan values into the form: data-ded="2000" data-copay="10".
  var deductible = parseFloat(form.dataset.ded);
  var copayPercent = parseFloat(form.dataset.copay);
  var amountBox = document.getElementById("eligible_amount");
  var copayText = document.getElementById("pv-copay");
  var payoutText = document.getElementById("pv-payout");

  amountBox.addEventListener("input", function () {
    var eligible = parseFloat(amountBox.value);

    // Nothing (or nonsense) typed: show dashes.
    if (isNaN(eligible) || eligible <= 0) {
      copayText.textContent = "-";
      payoutText.textContent = "-";
      return;
    }
    var afterDeductible = eligible - Math.min(eligible, deductible);
    var copayAmount = afterDeductible * copayPercent / 100;
    copayText.textContent = "-" + formatRupees(copayAmount);
    payoutText.textContent = formatRupees(afterDeductible - copayAmount);
  });
}


// ---------------------------------------------------------------------------
// 4. "Show password" checkboxes
// ---------------------------------------------------------------------------
/**
 * Any checkbox with data-show-password="box_id other_box_id" shows or hides the text
 * of those password boxes (it switches the input type between "password" and "text").
 * Used on the login page and on the change-password page.
 */
function setupShowPassword() {
  var checkboxes = document.querySelectorAll("[data-show-password]");
  checkboxes.forEach(function (checkbox) {
    var boxIds = checkbox.dataset.showPassword.split(" ");   // "a b c" -> ["a", "b", "c"]

    checkbox.addEventListener("change", function () {
      boxIds.forEach(function (id) {
        var box = document.getElementById(id);
        if (box) {
          box.type = checkbox.checked ? "text" : "password";
        }
      });
    });
  });
}


// ---------------------------------------------------------------------------
// 5. Change-password page: strength hint and "do they match?" hint
// ---------------------------------------------------------------------------
/**
 * Give a simple strength score from 0 to 4 for a password.
 * One point each for: 8+ characters, a lowercase AND an uppercase letter,
 * a digit, and a symbol. (A hint only - the server just requires 8+ characters.)
 */
function passwordScore(password) {
  var score = 0;
  if (password.length >= 8) { score++; }
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) { score++; }
  if (/[0-9]/.test(password)) { score++; }
  if (/[^A-Za-z0-9]/.test(password)) { score++; }
  return score;
}

/** Write a message with a Bootstrap colour class (text-danger, text-success...) into an element. */
function showHint(element, message, colorClass) {
  element.textContent = message;
  element.className = "small mb-3 " + colorClass;
}

/** Wire up the two live hints under the "new password" and "confirm password" boxes. */
function setupPasswordHints() {
  var newBox = document.getElementById("new_password");
  var confirmBox = document.getElementById("confirm_password");
  var strengthHint = document.getElementById("strength-hint");
  var matchHint = document.getElementById("match-hint");
  if (!newBox || !confirmBox) {
    return;     // not the change-password page
  }

  /** Update the strength message under the new password box. */
  function updateStrength() {
    var password = newBox.value;
    if (password.length === 0) {
      showHint(strengthHint, "At least 8 characters.", "text-muted");
    } else if (password.length < 8) {
      showHint(strengthHint, "Too short: " + password.length + " of 8 characters.", "text-danger");
    } else {
      var score = passwordScore(password);
      var words = ["", "Weak", "Fair", "Good", "Strong"];
      var color = score >= 3 ? "text-success" : "text-warning";
      var advice = score < 4 ? " (add capitals, numbers or symbols to improve)" : "";
      showHint(strengthHint, "Strength: " + words[score] + advice, color);
    }
  }

  /** Tell the user at once whether the two new passwords are equal. */
  function updateMatch() {
    if (confirmBox.value.length === 0) {
      showHint(matchHint, "", "text-muted");
    } else if (confirmBox.value === newBox.value) {
      showHint(matchHint, "Passwords match.", "text-success");
    } else {
      showHint(matchHint, "Passwords do not match yet.", "text-danger");
    }
  }

  newBox.addEventListener("input", function () { updateStrength(); updateMatch(); });
  confirmBox.addEventListener("input", updateMatch);
}


// ---------------------------------------------------------------------------
// Start everything once the page has loaded
// ---------------------------------------------------------------------------
/** Run every helper. Each one checks by itself whether the current page needs it. */
function setupPage() {
  showOnlyMembersOfPolicy();
  askBeforeClicking();
  showPayoutPreview();
  setupShowPassword();
  setupPasswordHints();
}

document.addEventListener("DOMContentLoaded", setupPage);
