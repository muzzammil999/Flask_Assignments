from flask import Flask, render_template, request, jsonify
import mysql.connector
from dotenv import load_dotenv
import os
import time

load_dotenv()

app = Flask(__name__)

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

TEA_TYPES = ["Regular", "Ginger", "Green","Elachi"]
PREP_TIMES = [2, 4, 6,8,10]


def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


def update_finished_orders():
    """Move finished active orders to Ready or Failed."""
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, tea_type, simulate_failure
        FROM orders
        WHERE status IN ('placed', 'processing')
          AND ready_at <= %s
    """, (time.time(),))

    orders = cursor.fetchall()

    for order in orders:
        if order["simulate_failure"]:
            reason = (
                "Ingredients are unavailable for "
                + order["tea_type"].lower()
                + " tea."
            )

            cursor.execute(
                """
                UPDATE orders
                SET status='failed', failure_reason=%s
                WHERE id=%s
                """,
                (reason, order["id"])
            )
        else:
            cursor.execute(
                "UPDATE orders SET status='ready' WHERE id=%s",
                (order["id"],)
            )

    db.commit()
    cursor.close()
    db.close()


def order_to_dict(row):
    seconds_left = max(0, row["ready_at"] - time.time())

    return {
        "id": row["id"],
        "customer_name": row["customer_name"],
        "tea_type": row["tea_type"],
        "prep_seconds": row["prep_seconds"],
        "simulate_failure": bool(row["simulate_failure"]),
        "status": row["status"],
        "failure_reason": row["failure_reason"],
        "seconds_left": round(seconds_left, 2)
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data."}), 400

    name = str(data.get("customer_name", "")).strip()
    tea = data.get("tea_type")
    prep = data.get("prep_seconds")
    failure = data.get("simulate_failure")

    if not 2 <= len(name) <= 50:
        return jsonify({"error": "Name must be 2 to 50 characters."}), 400

    if tea not in TEA_TYPES:
        return jsonify({"error": "Invalid tea type."}), 400

    if prep not in PREP_TIMES:
        return jsonify({"error": "Preparation time must be 2, 4, or 6 seconds."}), 400

    if not isinstance(failure, bool):
        return jsonify({"error": "Invalid failure value."}), 400

    ready_at = time.time() + prep

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

    db.commit()
    order_id = cursor.lastrowid

    cursor.close()
    db.close()

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
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        """
        UPDATE orders
        SET status='processing'
        WHERE id=%s AND status='placed'
        """,
        (order_id,)
    )

    db.commit()

    cursor.close()
    db.close()

    return jsonify({
        "message": "Order is processing."
    })


@app.route("/api/orders", methods=["GET"])
def get_orders():
    update_finished_orders()

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    rows = cursor.fetchall()

    cursor.close()
    db.close()

    return jsonify([order_to_dict(row) for row in rows])


@app.route("/api/orders/<int:order_id>")
def get_order(order_id):
    update_finished_orders()

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM orders WHERE id=%s",
        (order_id,)
    )
    row = cursor.fetchone()

    cursor.close()
    db.close()

    if row is None:
        return jsonify({"error": "Order not found."}), 404

    return jsonify(order_to_dict(row))


@app.errorhandler(500)
def server_error(error):
    print("Server error:", error)
    return jsonify({
        "error": "Server error. Check the Flask terminal."
    }), 500


if __name__ == "__main__":
    app.run(debug=True)
