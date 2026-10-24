document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".delete-event").forEach((button) => {
        button.addEventListener("click", async () => {
            const eventId = button.dataset.id;

            if (!confirm("Are you sure you want to delete this event?")) {
                return;
            }

            button.disabled = true;
            button.textContent = "Deleting...";

            try {
                const response = await fetch(`/api/events/${eventId}`, {
                    method: "DELETE"
                });

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.error || "Unable to delete event.");
                }

                window.location.href = result.redirect_url || "/";
            } catch (error) {
                alert(error.message);
                button.disabled = false;
                button.textContent = "Delete";
            }
        });
    });
});
