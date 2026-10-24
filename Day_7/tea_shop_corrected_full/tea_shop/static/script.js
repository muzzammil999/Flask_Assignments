// -------------------------
// HTML elements
// -------------------------

const form = document.getElementById("orderForm");
const nameInput = document.getElementById("customerName");
const teaInput = document.getElementById("teaType");
const timeInput = document.getElementById("prepTime");
const failureInput = document.getElementById("simulateFailure");
const errorBox = document.getElementById("formError");

const log = document.getElementById("activityLog");

const placedList = document.getElementById("listPlaced");
const processingList = document.getElementById("listProcessing");
const readyList = document.getElementById("listReady");
const failedList = document.getElementById("listFailed");

const placedCount = document.getElementById("countPlaced");
const processingCount = document.getElementById("countProcessing");
const readyCount = document.getElementById("countReady");
const failedCount = document.getElementById("countFailed");


// -------------------------
// Activity log
// -------------------------

function addLog(message, type = "info") {
    const item = document.createElement("li");

    const now = new Date();
    const time = now.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });

    item.innerHTML = `<span class="time">${time}</span>${message}`;
    item.classList.add(type);

    log.prepend(item);
}


// -------------------------
// Flask API helper
// -------------------------

async function api(url, options = {}) {
    const response = await fetch(url, options);

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Something went wrong.");
    }

    return data;
}


// -------------------------
// Show saved orders
// -------------------------

function showOrders(orders) {
    placedList.innerHTML = "";
    processingList.innerHTML = "";
    readyList.innerHTML = "";
    failedList.innerHTML = "";

    const placed = orders.filter(order => order.status === "placed");
    const processing = orders.filter(order => order.status === "processing");
    const ready = orders.filter(order => order.status === "ready");
    const failed = orders.filter(order => order.status === "failed");

    showList(placedList, placed);
    showList(processingList, processing);
    showList(readyList, ready);
    showList(failedList, failed);

    placedCount.textContent = placed.length;
    processingCount.textContent = processing.length;
    readyCount.textContent = ready.length;
    failedCount.textContent = failed.length;
}


function showList(element, orders) {
    if (orders.length === 0) {
        element.innerHTML = "<p class='muted'>No orders</p>";
        return;
    }

    orders.forEach(order => {
        const card = document.createElement("div");
        card.className = "order";

        card.innerHTML = `
            <b>#${order.id} · ${order.customer_name}</b>
            <span>${order.tea_type} tea · ${order.prep_seconds} seconds</span>
        `;

        if (order.status === "failed") {
            const reason = document.createElement("span");
            reason.className = "why";
            reason.textContent = order.failure_reason;
            card.appendChild(reason);
        }

        element.appendChild(card);
    });
}


// -------------------------
// Read orders from Flask
// -------------------------

async function loadOrders() {
    const orders = await api("/api/orders");
    showOrders(orders);
    return orders;
}


// -------------------------
// Promise + timer
// -------------------------

function prepareTea(order) {
    return new Promise((resolve, reject) => {
        setTimeout(() => {
            if (order.simulate_failure) {
                reject(new Error(
                    `Ingredients are unavailable for ${order.tea_type.toLowerCase()} tea.`
                ));
            } else {
                resolve(order);
            }
        }, order.seconds_left * 1000);
    });
}


// -------------------------
// Main asynchronous order flow
// -------------------------

async function processOrder(order) {
    try {
        // A newly placed order becomes Processing.
        if (order.status === "placed") {
            addLog(
                `${order.customer_name}'s ${order.tea_type} tea order is placed.`,
                "info"
            );

            await api(`/api/orders/${order.id}/processing`, {
                method: "PUT"
            });

            addLog(
                `${order.customer_name}'s ${order.tea_type} tea order is processing.`,
                "working"
            );
        }

        // Wait only inside this order's async function.
        await prepareTea(order);

        // Ask Flask for the current database status.
        const finished = await api(`/api/orders/${order.id}`);

        if (finished.status === "ready") {
            addLog(
                `${finished.customer_name}'s ${finished.tea_type} tea order is ready.`,
                "success"
            );
        }

        await loadOrders();

    } catch (error) {
        // The Promise was rejected because ingredients were unavailable.
        // loadOrders() also asks Flask to update the database to Failed.
        await loadOrders();

        addLog(
            `${order.customer_name}'s ${order.tea_type} tea order failed: ${error.message}`,
            "error"
        );
    }
}


// -------------------------
// Place a new order
// -------------------------

async function handleSubmit(event) {
    event.preventDefault();
    errorBox.hidden = true;

    const name = nameInput.value.trim();

    if (name.length < 2 || name.length > 50) {
        errorBox.textContent = "Name must be 2 to 50 characters.";
        errorBox.hidden = false;
        return;
    }

    const orderData = {
        customer_name: name,
        tea_type: teaInput.value,
        prep_seconds: Number(timeInput.value),
        simulate_failure: failureInput.checked
    };

    try {
        const order = await api("/api/orders", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(orderData)
        });

        // Start processing without waiting for it.
        processOrder(order);

        await loadOrders();

        nameInput.value = "";
        failureInput.checked = false;
        nameInput.focus();

    } catch (error) {
        errorBox.textContent = error.message;
        errorBox.hidden = false;
    }
}


// -------------------------
// Assignment demonstrations
// -------------------------

function brokenReturnDemo() {
    function tea() {
        setTimeout(() => {
            return "Ready";
        }, 2000);
    }

    const result = tea();

    addLog(
        `Broken return result: ${result}. The timer callback returns later.`,
        "demo"
    );

    addLog(
        "Next customer can continue immediately.",
        "demo"
    );
}


function callbackDemo() {
    function tea(done) {
        setTimeout(() => {
            done("Ready");
        }, 2000);
    }

    tea(value => {
        addLog(
            `Callback received: Tea is ${value}.`,
            "demo"
        );
    });

    addLog(
        "Callback: Next customer can continue immediately.",
        "demo"
    );
}


function promiseDemo() {
    function tea() {
        return new Promise(resolve => {
            setTimeout(() => {
                resolve("Ready");
            }, 2000);
        });
    }

    const promise = tea();

    addLog(
        `Promise returned immediately: ${promise}`,
        "demo"
    );

    promise.then(value => {
        addLog(
            `Promise finished: Tea is ${value}.`,
            "demo"
        );
    });

    addLog(
        "Promise: next line runs immediately.",
        "demo"
    );
}


// -------------------------
// Buttons
// -------------------------

form.addEventListener("submit", handleSubmit);

document.getElementById("demoBroken").addEventListener(
    "click",
    brokenReturnDemo
);

document.getElementById("demoCallback").addEventListener(
    "click",
    callbackDemo
);

document.getElementById("demoPromise").addEventListener(
    "click",
    promiseDemo
);

document.getElementById("clearLog").addEventListener("click", () => {
    log.innerHTML = "";
});


// -------------------------
// Start page
// -------------------------

async function start() {
    try {
        const orders = await loadOrders();

        // Continue orders that were still active when the page was refreshed.
        orders
            .filter(
                order =>
                    order.status === "placed" ||
                    order.status === "processing"
            )
            .forEach(order => processOrder(order));

    } catch (error) {
        addLog(
            `Could not load orders: ${error.message}`,
            "error"
        );
    }
}

start();
