"""
app.py - the Flask SERVER (backend) of the Tea Shop Order Simulator.

WHAT THIS FILE DOES (in very simple words)
------------------------------------------
Think of this file as the "kitchen manager" of the tea shop.

  * The browser (script.js) is the "cashier".
  * This file (Flask) is the "manager" who writes every order in a notebook.
  * MySQL is the "notebook" (the database) where orders are saved.

The cashier NEVER writes in the notebook directly.
The cashier always asks the manager (Flask) to do it, using an "API URL".

THE API URLs THIS FILE OFFERS
-----------------------------
    GET  /                          -> shows the web page (index.html)
    POST /api/orders                -> save a NEW order (status = placed)
    PUT  /api/orders/<id>/processing-> change an order to "processing"
    GET  /api/orders                -> give back ALL orders
    GET  /api/orders/<id>           -> give back ONE order

THE 4 ORDER STATUSES
--------------------
    placed      -> order is saved, work has not started yet
    processing  -> tea is being prepared
    ready       -> tea finished successfully
    failed      -> tea could not be made (ingredients unavailable)

NOTE FOR LEARNERS
-----------------
This Python file has NO async/await. Flask runs each request one after
another in plain, normal Python. All the "wait for later" magic
(Promises, setTimeout, await, callbacks) lives in static/script.js.
"""

# ----------------------------------------------------------------------
# IMPORTS  (tools we borrow from other Python packages)
# ----------------------------------------------------------------------
from flask import Flask, render_template, request, jsonify   # Flask web tools
import mysql.connector                                        # talk to MySQL
from dotenv import load_dotenv                                # read the .env file
import os                                                     # read env variables
import time                                                   # get the current time

# ----------------------------------------------------------------------
# SETUP  (runs ONE time when you start the server)
# ----------------------------------------------------------------------

# Step 1: Read the .env file so DB_HOST, DB_USER, etc. become available.
load_dotenv()

# Step 2: Create the Flask application object. "app" is the whole server.
app = Flask(__name__)

# Step 3: Read the database settings that were loaded from the .env file.
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# Step 4: The ONLY values we accept from the browser (used for validation).
TEA_TYPES = ["Regular", "Ginger", "Green", "Elachi"]
PREP_TIMES = [2, 4, 6, 9]   # preparation time in seconds


# ======================================================================
# HELPER FUNCTIONS
# ======================================================================

def get_db_connection():
    """
    Open a NEW connection to the MySQL database and return it.

    Simple idea:
        Like opening the door to the "notebook room".
        Whoever opens the door must close it later (db.close()).

    Steps:
        1. Use the host, user, password and database name from .env.
        2. Ask MySQL to open a connection.
        3. Hand the connection back to whoever called this function.

    Returns:
        A MySQL connection object. The caller must call .close() on it
        when finished.

    Example:
        db = get_db_connection()     # open the door
        cursor = db.cursor()         # take a pen
        ...                          # read / write
        cursor.close()               # put the pen down
        db.close()                   # close the door
    """
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


def update_finished_orders():
    """
    Look in the database for orders whose time is over, and mark them
    as "ready" or "failed".

    Why do we need this?
        Nobody is "watching the clock" inside the database.
        MySQL will not change a status by itself when time passes.
        So, every time the browser asks for orders, we FIRST call this
        function to refresh the statuses, and THEN return the orders.

    Steps (read top to bottom):
        1. Open a database connection.
        2. Find every order that is still "placed" or "processing"
           AND whose ready_at time is now or in the past.
        3. For each of those orders:
              - if simulate_failure is True  -> set status = 'failed'
                                                 and save a failure reason
              - otherwise                    -> set status = 'ready'
        4. Save (commit) all the changes.
        5. Close the cursor and the connection.

    Returns:
        Nothing (None). It only changes data inside the database.

    Example:
        An order has ready_at = 10:00:06.
        The browser asks for orders at 10:00:07.
        -> this function sees 10:00:06 <= 10:00:07
        -> the order becomes "ready" (or "failed" if simulate_failure).
    """
    # Step 1: open the connection. dictionary=True means each row comes
    # back like {"id": 1, "tea_type": "Green"} instead of (1, "Green").
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Step 2: find orders that are active AND whose time has finished.
    # %s is a safe placeholder; time.time() is "right now" in seconds.
    cursor.execute("""
        SELECT id, tea_type, simulate_failure
        FROM orders
        WHERE status IN ('placed', 'processing')
          AND ready_at <= %s
    """, (time.time(),))

    # Take all matching rows out of the cursor into a Python list.
    orders = cursor.fetchall()

    # Step 3: go through each finished order, one by one.
    for order in orders:
        if order["simulate_failure"]:
            # Build a friendly reason, e.g. "Ingredients are unavailable for ginger tea."
            reason = (
                "Ingredients are unavailable for "
                + order["tea_type"].lower()
                + " tea."
            )

            # Save "failed" and the reason in the database.
            cursor.execute(
                """
                UPDATE orders
                SET status='failed', failure_reason=%s
                WHERE id=%s
                """,
                (reason, order["id"])
            )
        else:
            # No failure was requested, so the tea is successfully ready.
            cursor.execute(
                "UPDATE orders SET status='ready' WHERE id=%s",
                (order["id"],)
            )

    # Step 4: without commit(), MySQL would forget all these changes.
    db.commit()

    # Step 5: always clean up.
    cursor.close()
    db.close()


def order_to_dict(row):
    """
    Convert ONE database row into a clean dictionary that can be sent
    to the browser as JSON.

    Why do we need this?
        - The database row has a column called ready_at (a clock time).
          The browser does not need that. It needs "seconds_left".
        - It also changes simulate_failure from 0/1 into False/True.

    Steps:
        1. Calculate how many seconds are left = ready_at - now.
           Never go below 0 (so we never show negative time).
        2. Build a dictionary with only the fields the browser needs.

    Args:
        row (dict): one row from the "orders" table
                    (the cursor was opened with dictionary=True).

    Returns:
        dict: the order in a browser-friendly format, for example
              {"id": 3, "customer_name": "Anu", "tea_type": "Green",
               "prep_seconds": 4, "simulate_failure": False,
               "status": "processing", "failure_reason": None,
               "seconds_left": 2.5}

    Example:
        ready_at = 100, now = 97   -> seconds_left = 3
        ready_at = 100, now = 105  -> seconds_left = 0 (not -5)
    """
    # Step 1: time left, but never negative.
    seconds_left = max(0, row["ready_at"] - time.time())

    # Step 2: build the dictionary that will become JSON.
    return {
        "id": row["id"],
        "customer_name": row["customer_name"],
        "tea_type": row["tea_type"],
        "prep_seconds": row["prep_seconds"],
        "simulate_failure": bool(row["simulate_failure"]),   # 0/1 -> False/True
        "status": row["status"],
        "failure_reason": row["failure_reason"],
        "seconds_left": round(seconds_left, 2)               # 2.4567 -> 2.46
    }


# ======================================================================
# ROUTES  (each @app.route is one URL the browser is allowed to call)
# ======================================================================
# A "decorator" is the line that starts with @ above a function.
# @app.route("/something") tells Flask:
#     "When the browser visits /something, run the function below."

@app.route("/")
def home():
    """
    Show the main web page.

    Called when:
        You open http://127.0.0.1:5000 in your browser.

    Steps:
        1. Find templates/index.html.
        2. Send that HTML page to the browser.
        3. The browser then loads static/script.js and static/style.css.

    Returns:
        The HTML of the page.
    """
    return render_template("index.html")


@app.route("/api/orders", methods=["POST"])
def create_order():
    """
    Save a BRAND NEW order in the database with status "placed".

    Called when:
        The cashier clicks "Place order". script.js sends a POST request
        (see handleSubmit in script.js).

    Steps:
        1. Read the JSON data sent by the browser.
        2. Check (validate) every value. Never trust the browser!
           If anything is wrong, stop and send back an error (HTTP 400).
        3. Calculate ready_at = current time + preparation seconds.
        4. Insert the order into MySQL with status 'placed'.
        5. Send the saved order back to the browser (HTTP 201 = Created).

    Returns:
        - Success: the new order as JSON, HTTP status 201.
        - Failure: {"error": "message"}, HTTP status 400.

    Why is validation done here, even though script.js checks the name too?
        Anyone can call this URL without using our page. The server
        must always protect itself.

    Example request body (what the browser sends):
        {"customer_name": "Anu", "tea_type": "Ginger",
         "prep_seconds": 6, "simulate_failure": false}
    """
    # Step 1: read the JSON. silent=True means "give me None if it is
    # broken JSON" instead of crashing.
    data = request.get_json(silent=True)

    # Step 2a: the JSON must be a dictionary (like {...}).
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data."}), 400

    # Pull out each value. .strip() removes extra spaces around the name.
    name = str(data.get("customer_name", "")).strip()
    tea = data.get("tea_type")
    prep = data.get("prep_seconds")
    failure = data.get("simulate_failure")

    # Step 2b: validate each value one by one.
    if not 2 <= len(name) <= 50:
        return jsonify({"error": "Name must be 2 to 50 characters."}), 400

    if tea not in TEA_TYPES:
        return jsonify({"error": "Invalid tea type."}), 400

    if prep not in PREP_TIMES:
        return jsonify({"error": "Preparation time must be 2, 4, or 6 seconds."}), 400

    if not isinstance(failure, bool):
        return jsonify({"error": "Invalid failure value."}), 400

    # Step 3: the exact clock time when this tea will be finished.
    ready_at = time.time() + prep

    # Step 4: save the order in MySQL.
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO orders
        (
            customer_name,
            tea_type,
            prep_seconds,
            simulate_failure,
            status,
            ready_at
        )
        VALUES (%s, %s, %s, %s, 'placed', %s)
    """, (name, tea, prep, failure, ready_at))

    db.commit()                    # make the INSERT permanent
    order_id = cursor.lastrowid    # the id MySQL gave to this new order

    cursor.close()
    db.close()

    # Step 5: reply to the browser. 201 means "created successfully".
    return jsonify({
        "id": order_id,
        "customer_name": name,
        "tea_type": tea,
        "prep_seconds": prep,
        "simulate_failure": failure,
        "status": "placed",
        "failure_reason": None,
        "seconds_left": prep
    }), 201


@app.route("/api/orders/<int:order_id>/processing", methods=["PUT"])
def start_processing(order_id):
    """
    Change ONE order from "placed" to "processing".

    Called when:
        processOrder() in script.js runs
        `await api("/api/orders/<id>/processing", {method: "PUT"})`.

    Steps:
        1. Open the database.
        2. Update the order ONLY IF it is currently 'placed'.
           (The "AND status='placed'" part stops us from moving a
            finished order backwards to 'processing'.)
        3. Save the change and close the database.
        4. Send a small confirmation message to the browser.

    Args:
        order_id (int): the number taken from the URL.
                        Example: /api/orders/7/processing -> order_id = 7

    Returns:
        {"message": "Order is processing."}
    """
    db = get_db_connection()
    cursor = db.cursor()

    # Step 2: only a 'placed' order is allowed to become 'processing'.
    cursor.execute(
        """
        UPDATE orders
        SET status='processing'
        WHERE id=%s AND status='placed'
        """,
        (order_id,)
    )

    db.commit()   # Step 3: save it

    cursor.close()
    db.close()

    # Step 4: confirm to the browser.
    return jsonify({
        "message": "Order is processing."
    })


@app.route("/api/orders", methods=["GET"])
def get_orders():
    """
    Return ALL orders (newest first) to the browser.

    Called when:
        loadOrders() in script.js runs (page start, after placing an
        order, after an order finishes).

    Steps:
        1. FIRST refresh statuses with update_finished_orders(), so
           finished orders show as ready / failed.
        2. Read every row from the orders table, newest first.
        3. Convert each row with order_to_dict().
        4. Send the list back as JSON.

    Returns:
        A JSON list, for example:
        [ {"id": 2, ...}, {"id": 1, ...} ]
    """
    # Step 1: bring the statuses up to date.
    update_finished_orders()

    # Step 2: read all orders. ORDER BY id DESC = newest on top.
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    rows = cursor.fetchall()

    cursor.close()
    db.close()

    # Steps 3 and 4: clean every row, then send the list as JSON.
    return jsonify([order_to_dict(row) for row in rows])


@app.route("/api/orders/<int:order_id>")
def get_order(order_id):
    """
    Return ONE order (found by its id) to the browser.

    Called when:
        processOrder() in script.js runs
        `await api("/api/orders/<id>")` after the waiting is over,
        to check the real final status stored in the database.

    Steps:
        1. Refresh statuses with update_finished_orders().
        2. Look for the order with this id.
        3. If it does not exist -> send an error with HTTP 404.
        4. Otherwise -> send the order as JSON.

    Args:
        order_id (int): taken from the URL. /api/orders/5 -> order_id = 5

    Returns:
        - Found:     the order as JSON.
        - Not found: {"error": "Order not found."} with HTTP 404.
    """
    # Step 1: bring statuses up to date.
    update_finished_orders()

    # Step 2: fetch the single order.
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM orders WHERE id=%s",
        (order_id,)
    )
    row = cursor.fetchone()   # one row, or None when nothing matches

    cursor.close()
    db.close()

    # Step 3: nothing found -> HTTP 404 "Not Found".
    if row is None:
        return jsonify({"error": "Order not found."}), 404

    # Step 4: found it.
    return jsonify(order_to_dict(row))


@app.errorhandler(500)
def server_error(error):
    """
    Catch any unexpected server crash (HTTP 500) and reply with JSON
    instead of an ugly HTML error page.

    Why JSON?
        script.js always calls response.json(). If the server returned
        HTML, that line would itself crash. A JSON error lets api() in
        script.js show a clean message.

    Steps:
        1. Print the real error in the Flask terminal (for you, the developer).
        2. Send a short, safe message to the browser.

    Args:
        error: the exception object Flask gives us.

    Returns:
        {"error": "Server error. Check the Flask terminal."}, HTTP 500
    """
    print("Server error:", error)
    return jsonify({
        "error": "Server error. Check the Flask terminal."
    }), 500


# ----------------------------------------------------------------------
# START THE SERVER
# ----------------------------------------------------------------------
# This block runs ONLY when you type:  python app.py
# debug=True restarts the server automatically when you edit the code
# and shows detailed errors. Use it only while learning, never in a real
# public website.
if __name__ == "__main__":
    app.run(debug=True)
