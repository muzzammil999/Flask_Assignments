# Tea Shop Order Simulator

## Files

```text
tea_shop/
├── app.py
├── schema.sql
├── .env
├── .env.example
├── requirements.txt
├── README.md
├── EXPLANATION.md
├── CONCEPTS.txt
├── templates/
│   └── index.html
└── static/
    ├── script.js
    └── style.css
```

## 1. Install Python packages

```bash
pip install -r requirements.txt
```

## 2. Configure MySQL

Open `.env` and put your real MySQL password:

```text
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=tea_shop
```

## 3. Create the database

Open MySQL Workbench or the MySQL command line.

Run the complete `schema.sql` file.

Then check:

```sql
USE tea_shop;
SHOW TABLES;
```

You should see:

```text
orders
```

## 4. Run Flask

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Order flow

```text
Place order
     ↓
JavaScript sends POST
     ↓
Flask
     ↓
MySQL saves order as "placed"
     ↓
JavaScript starts processOrder()
     ↓
Order becomes "processing"
     ↓
Promise + setTimeout
     ↓
Ready OR Failed
```

## Activity log examples

Successful order:

```text
Muzzammil's Ginger tea order is placed.
Muzzammil's Ginger tea order is processing.
Muzzammil's Ginger tea order is ready.
```

Failed order:

```text
Muzzammil's Ginger tea order is placed.
Muzzammil's Ginger tea order is processing.
Muzzammil's Ginger tea order failed: Ingredients are unavailable for ginger tea.
```

## Test the asynchronous behavior

1. Place a 6-second order.
2. Immediately place a 2-second order.
3. The 2-second order should become Ready first.
4. You can place another order while the first order is processing.
5. Check MySQL:

```sql
USE tea_shop;
SELECT * FROM orders ORDER BY id DESC;
```

## Test failure

Check:

```text
Simulate failure (ingredients unavailable)
```

The order should end in Failed while other orders continue normally.

## Test refresh

1. Place a 6-second order.
2. Refresh the browser while it is processing.
3. The order is read again from MySQL.
4. It continues toward its correct final state.

## Important JavaScript concepts

(For full explanations with tiny examples, read `CONCEPTS.txt`.
Every function in `app.py` and `static/script.js` also has a docstring
and numbered step-by-step comments.)

### setTimeout

Runs a function later.

### Callback

A function passed to another function and called later.

### Promise

Represents a result that will be available later.

### async

Allows a function to use `await`.

### await

Waits for a Promise inside the current async function.

### try/catch

Handles errors from the asynchronous operation.
