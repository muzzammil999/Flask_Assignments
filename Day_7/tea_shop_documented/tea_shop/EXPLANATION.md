# EXPLANATION.md

1. Returning inside `setTimeout()` does not return the tea from the outer function because the timer callback runs later, after the outer function has already finished.
2. A Promise returns immediately as an object that represents a result that will be available later.
3. `await` pauses the current `async` function until its Promise finishes; it does not freeze the whole webpage.
4. A later order can finish first because each order has its own timer and asynchronous function, so a 2-second order can finish before an earlier 6-second order.
5. In the main order flow, `fetch()` uses HTTP status to detect a server/API error, while `prepareTea()` can reject its Promise when the simulated ingredients failure happens.
6. The order states are stored in MySQL as `placed`, `processing`, `ready`, or `failed`, so the state can be restored after a browser refresh.
7. The activity log makes the sequence visible: the order is placed, then processing starts, and finally the order becomes ready or failed.
8. `processOrder(order)` is intentionally started without `await` in `handleSubmit()`, so the cashier can place another order immediately.




// ======================================================================
// SECTION 9: TEACHING DEMONSTRATIONS (the three small chip buttons)
// ======================================================================
// These do NOT use Flask or MySQL. They only show, with tiny examples,
// how waiting works in JavaScript. Click them and watch the
// Activity log to see the ORDER in which things happen.

/**
 * DEMO 1 - "Broken return". Shows WHY a normal `return` cannot give
 * you a delayed result.
 *
 * What you will see in the log:
 *   "Broken return result: undefined ..."   (appears immediately)
 *   "Next customer can continue immediately." (appears immediately)
 *   ...and the "Ready" is lost forever (it is never shown anywhere).
 *
 * Steps:
 *   1. Inside, define tea(): it starts a timer for 2 seconds.
 *   2. Call tea(). It finishes at once and returns NOTHING (undefined),
 *      because its only job was to start the timer.
 *   3. The timer's callback `return "Ready"` happens 2 seconds LATER,
 *      and it returns to the timer, NOT to the line that called tea().
 *   4. So `result` is undefined. Write that in the log.
 *
 * Lesson: a normal return cannot carry a result that arrives later.
 * Fix: use a callback (demo 2) or a Promise (demo 3).
 */
function brokenReturnDemo() {

    function tea() {
        // Step 1: start a 2-second timer, then the function ENDS.
        setTimeout(() => {
            return "Ready";     // goes nowhere useful (see step 3 in the doc above)
        }, 2000);
        // No return here, so tea() gives back undefined.
    }

    // Step 2: call tea() and take what it returned.
    const result = tea();

    // Step 4: result is undefined, not "Ready".
    addLog(
        `Broken return result: ${result}. The timer callback returns later.`,
        "demo"
    );

    addLog(
        "Next customer can continue immediately.",
        "demo"
    );
}


/**
 * DEMO 2 - "Callback". The OLD way to receive a delayed result.
 *
 * Simple idea:
 *   You give tea() a function called `done`. It means:
 *   "When the tea is ready, call this function and give it the result."
 *
 * What you will see in the log (in this order):
 *   1. "Callback: Next customer can continue immediately."  (instantly)
 *   2. "Callback received: Tea is Ready."                    (after 2 sec)
 *
 * Notice that line 1 shows up BEFORE line 2 even though the code that
 * writes line 2 is written first. This is because the callback runs
 * later.
 *
 * Steps:
 *   1. Define tea(done): it starts a 2-second timer.
 *   2. Call tea() and pass a callback function: value => { ... }
 *   3. tea() ends immediately. JavaScript goes to the next line.
 *   4. Write "Next customer can continue immediately." in the log.
 *   5. Two seconds later the timer calls done("Ready"), which runs our
 *      callback, which writes "Callback received: ..." in the log.
 *
 * Downside of callbacks: with many steps in a row, you get callbacks
 * inside callbacks inside callbacks ("callback hell"). Promises fix this.
 */
function callbackDemo() {

    // `done` is the callback function that the caller gives us.
    function tea(done) {
        setTimeout(() => {
            done("Ready");   // Step 5: call the callback with the result
        }, 2000);
    }

    // Step 2: pass in a function. It is NOT run now, it is run later.
    tea(value => {
        addLog(
            `Callback received: Tea is ${value}.`,
            "demo"
        );
    });

    // Step 4: this line runs BEFORE the callback above.
    addLog(
        "Callback: Next customer can continue immediately.",
        "demo"
    );
}


/**
 * DEMO 3 - "Promise .then()". The better way to receive a delayed
 * result.
 *
 * Simple idea:
 *   tea() hands you a PROMISE (a ticket) immediately. You attach a
 *   function with .then(). It is called when the ticket is fulfilled.
 *
 * What you will see in the log (in this order):
 *   1. "Promise returned immediately: [object Promise]" (instantly)
 *   2. "Promise: next line runs immediately."           (instantly)
 *   3. "Promise finished: Tea is Ready."                (after 2 sec)
 *
 * "[object Promise]" is just how JavaScript prints a Promise as text.
 * It proves that we got the TICKET, not the tea.
 *
 * Steps:
 *   1. Define tea(): it returns a new Promise that resolves with
 *      "Ready" after 2 seconds.
 *   2. Call tea(). We immediately receive the Promise (pending).
 *   3. Write the Promise itself in the log.
 *   4. Register promise.then(callback). The callback is saved and will
 *      run only when the Promise is fulfilled.
 *   5. Write "next line runs immediately." in the log.
 *   6. After 2 seconds the Promise is fulfilled, so the .then()
 *      callback runs and writes "Promise finished" in the log.
 *
 * Compare with async/await (used in processOrder). This code:
 *       const value = await tea();
 *       addLog(`Tea is ${value}`);
 *   does the same as .then(), but is easier to read from top to bottom.
 */
function promiseDemo() {

    // Step 1: a function that returns a Promise.
    function tea() {
        return new Promise(resolve => {
            setTimeout(() => {
                resolve("Ready");   // Step 6: fulfil the Promise
            }, 2000);
        });
    }

    // Step 2: we get the ticket instantly (state: pending).
    const promise = tea();

    // Step 3: shows "[object Promise]", not "Ready".
    addLog(
        `Promise returned immediately: ${promise}`,
        "demo"
    );

    // Step 4: "when you are fulfilled, run this function".
    promise.then(value => {
        addLog(
            `Promise finished: Tea is ${value}.`,
            "demo"
        );
    });

    // Step 5: runs BEFORE the .then() callback.
    addLog(
        "Promise: next line runs immediately.",
        "demo"
    );
}

