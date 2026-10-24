document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("registration-form");
    const errorBox = document.getElementById("form-error");

    if (!form) {
        return;
    }

    function showError(message) {
        errorBox.textContent = message;
        errorBox.classList.remove("hidden");
    }

    function clearError() {
        errorBox.textContent = "";
        errorBox.classList.add("hidden");
    }

    form.querySelectorAll("input, select").forEach((field) => {
        field.addEventListener("input", clearError);
        field.addEventListener("change", clearError);
    });

    form.addEventListener("submit", (event) => {
        clearError();

        const fullName = document.getElementById("full_name").value.trim();
        const email = document.getElementById("email").value.trim();
        const mobile = document.getElementById("mobile").value.trim();
        const seats = document.getElementById("seats_requested").value;

        if (!fullName || !email || !mobile || !seats) {
            event.preventDefault();
            showError("Please fill in all required fields.");
            return;
        }

        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

        if (!emailPattern.test(email)) {
            event.preventDefault();
            showError("Please enter a valid email address.");
            return;
        }

        if (!/^\d{10}$/.test(mobile)) {
            event.preventDefault();
            showError("Mobile number must contain exactly 10 digits.");
        }
    });
});
