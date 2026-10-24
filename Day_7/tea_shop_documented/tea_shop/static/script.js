/**
 * script.js - the BROWSER side (frontend) of the Tea Shop Order Simulator.
 *
 * ======================================================================
 * BIG PICTURE (very simple)
 * ======================================================================
 * This file is the "cashier". It:
 *   1. Reads what the customer typed in the form.
 *   2. Asks Flask (the manager) to save the order.
 *   3. Waits for the tea to be ready WITHOUT freezing the page.
 *   4. Shows the order on the screen and writes messages in the log.
 *
 * ======================================================================
 * THE MOST IMPORTANT IDEA IN THIS FILE
 * ======================================================================
 * Some things take TIME (making tea, asking the server).
 * JavaScript does NOT stand still and wait. It says:
 *     "Tell me when you are done. Meanwhile I will continue my work."
 *
 * There are 3 ways to say "tell me when you are done":
 *     1. CALLBACK  -> hand over a function, "call this when finished".
 *     2. PROMISE   -> receive a "ticket" now, the result comes later.
 *     3. ASYNC / AWAIT -> write Promise code so it reads top-to-bottom.
 *
 * Real-life example: ordering food at a restaurant.
 *     - Callback : "Call my phone when the food is ready."
 *     - Promise  : You get a token number (the ticket) immediately.
 *     - await    : You sit at your table and wait for the token to be
 *                  called. But the restaurant keeps serving other people!
 *
 * See CONCEPTS.txt (in the main folder) for more tiny examples.
 *
 * ======================================================================
 * HOW A WHOLE ORDER TRAVELS (follow the numbers)
 * ======================================================================
 *   1. handleSubmit()   : cashier clicks "Place order"
 *   2. api() POST       : Flask saves the order as "placed"
 *   3. processOrder()   : starts (NOT awaited, so cashier is free)
 *   4. api() PUT        : Flask changes it to "processing"
 *   5. prepareTea()     : Promise + setTimeout = the waiting
 *   6. api() GET        : Flask says "ready" or "failed"
 *   7. loadOrders()     : the screen is refreshed
 */


// ======================================================================
// SECTION 1: HTML ELEMENTS
// ======================================================================
// document.getElementById("x") finds the HTML tag that has id="x".
// We do it ONE time here and keep the result in a constant, so every
// function below can use it.

// --- the order form and its fields ---
const form = document.getElementById("orderForm");
const nameInput = document.getElementById("customerName");
const teaInput = document.getElementById("teaType");
const timeInput = document.getElementById("prepTime");
const failureInput = document.getElementById("simulateFailure");
const errorBox = document.getElementById("formError");

// --- the activity log (the <ul> list of messages) ---
const log = document.getElementById("activityLog");

// --- the four boxes where orders are shown ---
const placedList = document.getElementById("listPlaced");
const processingList = document.getElementById("listProcessing");
const readyList = document.getElementById("listReady");
const failedList = document.getElementById("listFailed");

// --- the small number badges (the count next to each heading) ---
const placedCount = document.getElementById("countPlaced");
const processingCount = document.getElementById("countProcessing");
const readyCount = document.getElementById("countReady");
const failedCount = document.getElementById("countFailed");


// ======================================================================
// SECTION 2: ACTIVITY LOG
// ======================================================================

/**
 * Add ONE new message at the TOP of the Activity log.
 *
 * Simple idea:
 *   Like writing a new line in a diary, with the current time in front.
 *   This is how we SEE the order of events (what happened first, what
 *   happened later).
 *
 * This is a normal (synchronous) function: it finishes instantly.
 *
 * Steps:
 *   1. Create a new empty list item (<li>).
 *   2. Get the current time as text, like "10:42:07 AM".
 *   3. Put the time and the message inside the <li>.
 *   4. Give the <li> a CSS class (info / working / success / error /
 *      demo) so it gets the right colour.
 *   5. Put the <li> at the TOP of the list (prepend).
 *
 * @param {string} message - the text to show.
 * @param {string} [type="info"] - colour style:
 *        "info", "working", "success", "error" or "demo".
 *
 * Example:
 *   addLog("Anu's Green tea order is ready.", "success");
 */
function addLog(message, type = "info") {
    // Step 1: make an empty <li></li>
    const item = document.createElement("li");

    // Step 2: current time as readable text.
    const now = new Date();
    const time = now.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });

    // Step 3: fill the <li> with the time and the message.
    item.innerHTML = `<span class="time">${time}</span>${message}`;

    // Step 4: add the colour class.
    item.classList.add(type);

    // Step 5: newest message goes on top.
    log.prepend(item);
}


// ======================================================================
// SECTION 3: TALKING TO FLASK
// ======================================================================

/**
 * ASYNC FUNCTION - Send a request to Flask and get the answer back.
 * Every other function uses this one to talk to the server.
 *
 * Why is it "async"?
 *   Asking a server takes time (a few milliseconds, sometimes more).
 *   An async function ALWAYS returns a PROMISE immediately.
 *   The real answer arrives later, when the server replies.
 *
 * What does "await" do here?
 *   `await` means: "Pause THIS function until the answer comes."
 *   Important: only THIS function pauses. The rest of the web page
 *   (buttons, typing, other orders) keeps working normally.
 *
 * Steps (follow the numbers; each `await` is a small waiting point):
 *   1. fetch(url, options)  -> send the request.
 *      WAIT here until the server starts replying.
 *   2. response.json()      -> turn the reply text into a JS object.
 *      WAIT here again until the whole reply is read.
 *   3. If the server said "not OK" (for example error 400 or 404),
 *      THROW an Error with the server's message.
 *   4. Otherwise RETURN the data.
 *
 * About errors:
 *   - `throw` inside an async function turns the returned Promise into
 *     a REJECTED Promise. The caller catches it with try/catch.
 *   - fetch() does NOT fail on HTTP 400/404/500. It only fails if the
 *     internet/server is unreachable. That is why we check
 *     `response.ok` ourselves in step 3.
 *
 * @param {string} url - the Flask address, e.g. "/api/orders".
 * @param {object} [options={}] - method, headers, body (optional).
 *        If left empty, fetch() makes a normal GET request.
 * @returns {Promise<any>} Promise that gives the data sent by Flask.
 *
 * Example:
 *   const orders = await api("/api/orders");
 *   // ...the line below runs only AFTER the answer has arrived
 *   console.log(orders);
 */
async function api(url, options = {}) {
    // Step 1: send the request and WAIT for the server's reply.
    const response = await fetch(url, options);

    // Step 2: read the reply body as JSON and WAIT until it is ready.
    const data = await response.json();

    // Step 3: response.ok is true for status 200-299, false otherwise.
    if (!response.ok) {
        // Use Flask's message if there is one, else a general message.
        throw new Error(data.error || "Something went wrong.");
    }

    // Step 4: success! This value becomes the Promise's result.
    return data;
}


// ======================================================================
// SECTION 4: SHOWING ORDERS ON THE SCREEN
// ======================================================================

/**
 * Draw ALL orders on the screen, sorted into the four boxes
 * (Placed / Processing / Ready / Failed) and update the counters.
 *
 * Simple idea:
 *   Erase the four boxes, then fill them again with fresh data.
 *   This is a normal (synchronous) function.
 *
 * Steps:
 *   1. Empty the four boxes.
 *   2. Split the orders into four groups using .filter().
 *   3. Let showList() draw each group in its own box.
 *   4. Write the number of orders in each group in the counters.
 *
 * About the arrow function `order => order.status === "placed"`:
 *   It is a tiny CALLBACK. .filter() calls it once for every order.
 *   If it answers true the order stays in the group, if false it is left out.
 *
 * @param {Array<object>} orders - list of orders received from Flask.
 *
 * Example:
 *   showOrders([{id:1, status:"ready", ...}, {id:2, status:"placed", ...}]);
 *   // -> Ready box shows #1, Placed box shows #2, counters 1 and 1
 */
function showOrders(orders) {
    // Step 1: clear old content.
    placedList.innerHTML = "";
    processingList.innerHTML = "";
    readyList.innerHTML = "";
    failedList.innerHTML = "";

    // Step 2: make four groups (each filter callback runs once per order).
    const placed = orders.filter(order => order.status === "placed");
    const processing = orders.filter(order => order.status === "processing");
    const ready = orders.filter(order => order.status === "ready");
    const failed = orders.filter(order => order.status === "failed");

    // Step 3: draw each group in its own box.
    showList(placedList, placed);
    showList(processingList, processing);
    showList(readyList, ready);
    showList(failedList, failed);

    // Step 4: update the number badges.
    placedCount.textContent = placed.length;
    processingCount.textContent = processing.length;
    readyCount.textContent = ready.length;
    failedCount.textContent = failed.length;
}


/**
 * Draw the order cards for ONE box (for example only the Ready box).
 * This is a normal (synchronous) function.
 *
 * Steps:
 *   1. If the group is empty, show "No orders" and stop (return).
 *   2. Otherwise, for each order make a small card (<div>).
 *   3. Put the order number, name, tea type and seconds in the card.
 *   4. If the order failed, add the failure reason to the card.
 *   5. Put the card inside the box.
 *
 * About `orders.forEach(order => { ... })`:
 *   The arrow function is a CALLBACK. forEach calls it one time for
 *   every order in the list.
 *
 * @param {HTMLElement} element - the box to fill (e.g. readyList).
 * @param {Array<object>} orders - only the orders that belong in the box.
 */
function showList(element, orders) {
    // Step 1: nothing to show.
    if (orders.length === 0) {
        element.innerHTML = "<p class='muted'>No orders</p>";
        return;   // stop here, the rest of the function is skipped
    }

    // Step 2: one card per order.
    orders.forEach(order => {
        const card = document.createElement("div");
        card.className = "order";

        // Step 3: card content, e.g. "#4 · Anu" and "Green tea · 6 seconds".
        card.innerHTML = `
            <b>#${order.id} · ${order.customer_name}</b>
            <span>${order.tea_type} tea · ${order.prep_seconds} seconds</span>
        `;

        // Step 4: failed orders also show WHY they failed.
        if (order.status === "failed") {
            const reason = document.createElement("span");
            reason.className = "why";
            // textContent (not innerHTML) is safer for text from outside.
            reason.textContent = order.failure_reason;
            card.appendChild(reason);
        }

        // Step 5: place the finished card inside the box.
        element.appendChild(card);
    });
}


// ======================================================================
// SECTION 5: LOADING ORDERS FROM FLASK
// ======================================================================

/**
 * ASYNC FUNCTION - Ask Flask for all saved orders and draw them.
 *
 * Simple idea:
 *   "Flask, please give me the latest list of orders" -> then show it.
 *
 * Steps:
 *   1. await api("/api/orders")  -> WAIT for Flask to send the list.
 *      (Flask also updates old orders to ready/failed at this moment.)
 *   2. showOrders(orders)        -> draw them on the screen.
 *   3. return orders             -> hand the list to whoever called us.
 *
 * Because it is async, it returns a Promise. The Promise's value is the
 * `orders` list.
 *
 * @returns {Promise<Array<object>>} the list of orders.
 *
 * Example:
 *   const orders = await loadOrders();
 *   console.log(orders.length);   // runs after the list is drawn
 */
async function loadOrders() {
    // Step 1: WAIT for the answer from the server.
    const orders = await api("/api/orders");

    // Step 2: runs only after step 1 has finished.
    showOrders(orders);

    // Step 3: give the list back to the caller.
    return orders;
}


// ======================================================================
// SECTION 6: PROMISE + TIMER (the "waiting" part)
// ======================================================================

/**
 * PROMISE FUNCTION - Pretend to prepare the tea. Takes time.
 *
 * Simple idea:
 *   This function gives you a "ticket" (a Promise) RIGHT AWAY.
 *   When the tea is finished, the ticket is settled:
 *       - resolve(order) -> "Success! Tea is ready."
 *       - reject(error)  -> "Sorry, it failed."
 *
 * Why not just use `return` inside setTimeout?
 *   A `return` inside setTimeout's callback goes nowhere. By the time
 *   the timer runs, the outer function finished long ago. A Promise
 *   solves this: it is a box that can be opened later.
 *
 * The 3 states of a Promise:
 *     pending   -> still waiting (the timer is running)
 *     fulfilled -> resolve() was called  (success)
 *     rejected  -> reject() was called   (failure)
 *   Once it is fulfilled or rejected it can never change again.
 *
 * Steps:
 *   1. Create `new Promise(...)`. JavaScript runs the function inside
 *      it immediately, and gives us two helpers: resolve and reject.
 *   2. Start a timer with setTimeout. The timer is told:
 *      "Run this callback after seconds_left x 1000 milliseconds."
 *   3. The function returns the Promise RIGHT NOW (still pending).
 *      Nothing is blocked while the timer counts down.
 *   4. Later, when the time is over, the timer calls our callback:
 *        - simulate_failure is true  -> reject(new Error(...))
 *        - otherwise                 -> resolve(order)
 *
 * Why `seconds_left * 1000`?
 *   setTimeout counts in MILLISECONDS. 1 second = 1000 ms.
 *   (seconds_left comes from Flask. If you refresh the page, it is the
 *   REMAINING time, so the order does not start from zero again.)
 *
 * @param {object} order - the order (needs seconds_left, simulate_failure,
 *                         tea_type).
 * @returns {Promise<object>} resolves with the order, or rejects with an
 *                            Error ("Ingredients are unavailable ...").
 *
 * Example:
 *   const ticket = prepareTea(order);   // ticket is "pending" right now
 *   await ticket;                       // wait here, but only this function
 */
function prepareTea(order) {
    // Step 1: create the Promise. `resolve` and `reject` are the two
    // buttons we may press later.
    return new Promise((resolve, reject) => {

        // Step 2: setTimeout(callback, delayInMilliseconds)
        // The arrow function below is the CALLBACK. JavaScript calls it
        // later, when the delay is over.
        setTimeout(() => {

            // Step 4: the time is over, decide the result.
            if (order.simulate_failure) {
                // Failure -> the Promise becomes REJECTED.
                reject(new Error(
                    `Ingredients are unavailable for ${order.tea_type.toLowerCase()} tea.`
                ));
            } else {
                // Success -> the Promise becomes FULFILLED.
                resolve(order);
            }

        }, order.seconds_left * 1000);   // delay in milliseconds

        // Step 3: the function ends here. The Promise is returned
        // immediately, the timer keeps running in the background.
    });
}


// ======================================================================
// SECTION 7: THE MAIN ORDER FLOW
// ======================================================================

/**
 * ASYNC FUNCTION - The complete life of ONE order, from "placed" to
 * "ready" or "failed". This is the MOST IMPORTANT function in the file.
 *
 * Simple idea:
 *   Every order gets its OWN private copy of this function running.
 *   If 3 orders are placed, 3 copies run at the same time, each
 *   waiting for its own timer. That is why a 2-second order can finish
 *   BEFORE an earlier 6-second order.
 *
 * What does `await` do in this function?
 *   `await X` = "Pause THIS copy of the function until X finishes.
 *   Let the browser do other things in the meantime."
 *   It does NOT freeze the page or other orders.
 *
 * What does try / catch do?
 *   try   { code that may fail }
 *   catch { what to do if it fails }
 *   If any awaited Promise is REJECTED (or an error is thrown),
 *   JavaScript jumps straight from that line down to catch.
 *
 * Steps in the TRY block:
 *   1. (Only if the order is brand new, status "placed")
 *        a. Write "order is placed" in the log.
 *        b. await the PUT request: Flask sets status = "processing".
 *           WAIT 1 - for the server's answer.
 *        c. Write "order is processing" in the log.
 *   2. await prepareTea(order): the real waiting (the timer).
 *      WAIT 2 - until the Promise is fulfilled (or rejected -> catch).
 *   3. await api(GET one order): ask Flask for the final saved status.
 *      WAIT 3 - for the server's answer.
 *   4. If the status is "ready", write "order is ready" in the log.
 *   5. await loadOrders(): redraw the boxes.
 *      WAIT 4 - for the list and the redraw.
 *
 * Steps in the CATCH block (something went wrong):
 *   6. await loadOrders(): ask Flask for the list. This also makes
 *      Flask mark the order as "failed" in the database, and then the
 *      screen is redrawn.
 *   7. Write "order failed: <reason>" in the log.
 *
 * Why does this function never crash the page?
 *   It catches its own errors, so nobody needs to catch them outside.
 *   That is why handleSubmit() can safely start it without await.
 *
 * Why `if (order.status === "placed")`?
 *   After a page refresh, an order may already be "processing". We must
 *   NOT announce "placed" or send the PUT request a second time. We
 *   only continue to wait for it.
 *
 * @param {object} order - the order object received from Flask.
 * @returns {Promise<void>} a Promise that finishes when the order is
 *                          completely done (ready or failed). Nothing
 *                          is returned as a value.
 *
 * Example of the log for a 6-second Ginger tea order:
 *   10:00:00  Anu's Ginger tea order is placed.
 *   10:00:00  Anu's Ginger tea order is processing.
 *   10:00:06  Anu's Ginger tea order is ready.
 */
async function processOrder(order) {
    try {
        // ---------- Step 1: only for a NEW order ----------
        if (order.status === "placed") {

            // 1a: first message in the log.
            addLog(
                `${order.customer_name}'s ${order.tea_type} tea order is placed.`,
                "info"
            );

            // 1b: WAIT 1 - tell Flask to change status to "processing".
            await api(`/api/orders/${order.id}/processing`, {
                method: "PUT"
            });

            // 1c: runs only AFTER the server has answered.
            addLog(
                `${order.customer_name}'s ${order.tea_type} tea order is processing.`,
                "working"
            );
        }

        // ---------- Step 2: the real waiting ----------
        // WAIT 2 - pause only THIS order's function until the timer ends.
        // If the Promise is rejected, JS jumps to catch below.
        await prepareTea(order);

        // ---------- Step 3: ask the database for the final status ----------
        // WAIT 3 - Flask checks the time and returns the true status.
        const finished = await api(`/api/orders/${order.id}`);

        // ---------- Step 4: announce success ----------
        if (finished.status === "ready") {
            addLog(
                `${finished.customer_name}'s ${finished.tea_type} tea order is ready.`,
                "success"
            );
        }

        // ---------- Step 5: redraw the screen ----------
        // WAIT 4 - refresh all four boxes.
        await loadOrders();

    } catch (error) {
        // ---------- Something failed ----------
        // Reasons: prepareTea() was rejected (ingredients unavailable),
        // OR the server could not be reached.
        // The line below runs ONLY when an error happened.

        // Step 6: loadOrders() also asks Flask to update the database to
        // "failed", then redraws the screen.
        await loadOrders();

        // Step 7: tell the user what went wrong.
        addLog(
            `${order.customer_name}'s ${order.tea_type} tea order failed: ${error.message}`,
            "error"
        );
    }
}


// ======================================================================
// SECTION 8: PLACING A NEW ORDER
// ======================================================================

/**
 * ASYNC FUNCTION - Runs when the cashier clicks "Place order".
 * This is an EVENT HANDLER: a function the browser calls (a CALLBACK)
 * whenever the form is submitted.
 *
 * Simple idea:
 *   Check the name -> send the order to Flask -> start the waiting in
 *   the background -> be ready for the next customer.
 *
 * THE KEY LINE:
 *       processOrder(order);      <- NO `await` in front on purpose!
 *   Without await, JavaScript starts the order's journey and moves on
 *   to the next line IMMEDIATELY. This is why the cashier can place
 *   another order while the first one is still being prepared.
 *   (If we wrote `await processOrder(order)`, handleSubmit would not
 *   finish until the tea is done: the form would not clear and the new
 *   order would not appear in the Placed box for up to 6 seconds.
 *   Try it to see the difference!)
 *
 * Steps:
 *   1. event.preventDefault(): stop the browser from reloading the page
 *      (a form normally reloads the page when submitted).
 *   2. Hide the old error message.
 *   3. Read and trim the name. If it is too short or too long, show an
 *      error and stop (return).
 *   4. Build the orderData object from the form fields.
 *   5. await api(POST): WAIT only until Flask has SAVED the order
 *      (a very short wait, not the tea preparation time!).
 *   6. Start processOrder(order) WITHOUT await. It runs in background.
 *   7. await loadOrders(): show the new order in the "Placed" box.
 *   8. Clear the name box, untick the checkbox, put the cursor back
 *      in the name box, ready for the next customer.
 *
 * If something fails (for example the server says "Invalid tea type"):
 *   catch -> show the message in the red error box.
 *
 * @param {Event} event - the "submit" event given by the browser.
 * @returns {Promise<void>} nothing useful is returned.
 */
async function handleSubmit(event) {
    // Step 1: stop the automatic page reload.
    event.preventDefault();

    // Step 2: hide any old error.
    errorBox.hidden = true;

    // Step 3: read the name (trim removes spaces at both ends).
    const name = nameInput.value.trim();

    if (name.length < 2 || name.length > 50) {
        errorBox.textContent = "Name must be 2 to 50 characters.";
        errorBox.hidden = false;
        return;   // stop here, do not send anything to Flask
    }

    // Step 4: collect the form data. Number() converts the text "6" to 6.
    const orderData = {
        customer_name: name,
        tea_type: teaInput.value,
        prep_seconds: Number(timeInput.value),
        simulate_failure: failureInput.checked   // true or false
    };

    try {
        // Step 5: WAIT only until Flask has saved the new order.
        const order = await api("/api/orders", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"   // we are sending JSON
            },
            // JSON.stringify turns the JS object into JSON text.
            body: JSON.stringify(orderData)
        });

        // Step 6: THE KEY LINE - start processing, do NOT wait for it.
        // processOrder handles its own errors, so this is safe.
        processOrder(order);

        // Step 7: show the new order right away in the "Placed" box.
        await loadOrders();

        // Step 8: get the form ready for the next customer.
        nameInput.value = "";
        failureInput.checked = false;
        nameInput.focus();

    } catch (error) {
        // Flask refused the order, or the server could not be reached.
        errorBox.textContent = error.message;
        errorBox.hidden = false;
    }
}



// ======================================================================
// SECTION 10: CONNECTING BUTTONS TO FUNCTIONS
// ======================================================================
// addEventListener("eventName", function) means:
//     "When this event happens, call this function later."
// The function we pass is a CALLBACK. We do NOT write () after its name,
// because we do not want to run it now, only give it to the browser.
//   handleSubmit    -> pass the function (correct)
//   handleSubmit()  -> run it right now (wrong here)

// When the form is submitted -> run handleSubmit.
form.addEventListener("submit", handleSubmit);

// Each demo chip button runs its own demo when clicked.
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

// "Clear log" button: the small arrow function is an inline callback.
// It simply empties the log list.
document.getElementById("clearLog").addEventListener("click", () => {
    log.innerHTML = "";
});


// ======================================================================
// SECTION 11: STARTING THE PAGE
// ======================================================================

/**
 * ASYNC FUNCTION - Runs ONE time when the page opens (or is refreshed).
 *
 * Simple idea:
 *   "Load the saved orders. If some orders were still being made when
 *   the page was closed or refreshed, continue waiting for them."
 *
 * This works because orders are stored in MySQL, not in the browser.
 * The browser forgets everything on refresh, but the database does not.
 *
 * Steps:
 *   1. await loadOrders(): WAIT for the saved orders, then draw them.
 *   2. Keep only the orders that are still "placed" or "processing".
 *   3. For each of them, start processOrder(order). No `await` is used,
 *      so all of them wait IN PARALLEL, each with its own timer.
 *      (Their seconds_left is the REMAINING time, so they do not
 *      restart from the beginning.)
 *
 * If loading fails (for example Flask is not running):
 *   catch -> write "Could not load orders: ..." in the log.
 *
 * @returns {Promise<void>} nothing useful is returned.
 *
 * Example:
 *   Place a 6-second order, refresh after 2 seconds.
 *   -> start() finds the order "processing" with about 4 seconds left
 *   -> processOrder waits 4 seconds -> the order becomes Ready.
 */
async function start() {
    try {
        // Step 1: WAIT for the saved orders (and draw them).
        const orders = await loadOrders();

        // Step 2 and 3: continue every unfinished order.
        orders
            .filter(
                // callback: keep only orders that are not finished
                order =>
                    order.status === "placed" ||
                    order.status === "processing"
            )
            // callback: start each one's journey, no await = parallel
            .forEach(order => processOrder(order));

    } catch (error) {
        addLog(
            `Could not load orders: ${error.message}`,
            "error"
        );
    }
}

// Call start() now, as the very last line of the file.
// (We do not await it here, there is nothing more to run afterwards.)
start();
