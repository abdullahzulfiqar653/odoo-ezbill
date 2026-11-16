/** @odoo-module **/

// Polls the transaction while the customer scans the Raast QR, then sends
// them to Odoo's payment status page. Plain DOM code, no framework needed.

const POLL_MS = 3000;
const TEXT = {
    done: "Payment received. Redirecting…",
    cancel: "This payment was cancelled or expired. Please go back and try again.",
    error: "The payment could not be completed. Please contact us.",
    expired: "This QR code has expired. Please go back and try again.",
};

function startEzbillPolling(card) {
    const pollUrl = card.dataset.pollUrl;
    const expiresAt = card.dataset.expiresAt ? Date.parse(card.dataset.expiresAt) : NaN;
    const statusText = card.querySelector(".o_ezbill_status_text");
    const spinner = card.querySelector(".o_ezbill_status .spinner-border");
    let stopped = false;

    const stop = (message, cls) => {
        stopped = true;
        if (spinner) spinner.remove();
        if (statusText) {
            statusText.textContent = message;
            statusText.classList.add(cls);
        }
    };

    const tick = async () => {
        if (stopped) return;
        if (!Number.isNaN(expiresAt) && Date.now() > expiresAt + 60000) {
            stop(TEXT.expired, "text-danger");
            return;
        }
        try {
            const res = await fetch(pollUrl, { credentials: "same-origin", headers: { Accept: "application/json" } });
            if (res.ok) {
                const data = await res.json();
                if (data.state === "done" || data.state === "authorized") {
                    stop(TEXT.done, "text-success");
                    window.location.assign(data.redirect || "/payment/status");
                    return;
                }
                if (data.state === "cancel") {
                    stop(TEXT.cancel, "text-danger");
                    return;
                }
                if (data.state === "error") {
                    stop(data.message || TEXT.error, "text-danger");
                    return;
                }
            }
        } catch {
            // Network blip: keep polling.
        }
        setTimeout(tick, POLL_MS);
    };
    setTimeout(tick, POLL_MS);
}

function init() {
    document.querySelectorAll(".o_ezbill_card[data-poll-url]").forEach(startEzbillPolling);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
