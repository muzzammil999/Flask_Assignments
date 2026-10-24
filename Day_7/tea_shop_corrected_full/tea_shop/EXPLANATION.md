# EXPLANATION.md

1. Returning inside `setTimeout()` does not return the tea from the outer function because the timer callback runs later, after the outer function has already finished.
2. A Promise returns immediately as an object that represents a result that will be available later.
3. `await` pauses the current `async` function until its Promise finishes; it does not freeze the whole webpage.
4. A later order can finish first because each order has its own timer and asynchronous function, so a 2-second order can finish before an earlier 6-second order.
5. In the main order flow, `fetch()` uses HTTP status to detect a server/API error, while `prepareTea()` can reject its Promise when the simulated ingredients failure happens.
6. The order states are stored in MySQL as `placed`, `processing`, `ready`, or `failed`, so the state can be restored after a browser refresh.
7. The activity log makes the sequence visible: the order is placed, then processing starts, and finally the order becomes ready or failed.
8. `processOrder(order)` is intentionally started without `await` in `handleSubmit()`, so the cashier can place another order immediately.
