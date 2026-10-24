/*
 * Trip Planner front-end script. Loaded on every page by templates/base.html.
 * Its only job: on the trip form (the <form data-trip-form> in
 * templates/trip_form.html) keep "End date" from being earlier than "Start date".
 * The server re-checks this in validate_trip_form() (app.py), so this script is
 * only a convenience - the page still works with JavaScript turned off.
 */
document.addEventListener("DOMContentLoaded", () => {
  const tripForm = document.querySelector("[data-trip-form]");
  if (!tripForm) return; // not on the trip form page

  const start = document.getElementById("start_date");
  const end = document.getElementById("end_date");

  // Disable earlier end dates in the picker and flag an invalid pair.
  const updateEndMin = () => {
    if (start.value) end.min = start.value;
    if (start.value && end.value && end.value < start.value) {
      end.setCustomValidity("End date must be on or after start date.");
    } else {
      end.setCustomValidity(""); // clear the error so the form can submit
    }
  };
  start.addEventListener("change", updateEndMin);
  end.addEventListener("change", updateEndMin);
  updateEndMin(); // run once for the pre-filled edit form
});
