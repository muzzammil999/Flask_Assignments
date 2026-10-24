# MySQL Story CRUD: raw SQL and ORM

Two tiny Flask apps with the same screens and the same `stories` table. Run them on different ports to compare code and data. **No SQLite is used.** This is a classroom CRUD demo; it has no user accounts or ownership rules.

## Layout

- `raw_sql/app.py`: explicit `mysql.connector` connections, cursors, SQL, commit and rollback.
- `orm/app.py`: `Story` model, `db.session`, `select`, tracked changes, commit.
- `schema.sql`: one compatible MySQL table for both apps.
- Both `templates/` and `static/` folders are included in each app so they can be opened independently.

## Windows setup (PowerShell in the project root)

Install MySQL Server and ensure it is running. Create the database and table in MySQL Workbench by opening and executing `schema.sql`. Alternatively, from **Command Prompt** (not PowerShell), if `mysql` is on PATH:

```bat
mysql -u root -p < schema.sql
```

Create a virtual environment and install dependencies:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, use Command Prompt instead: `.venv\Scripts\activate.bat`. Edit `.env` with your own `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME`. Do not commit `.env`.

Start the raw SQL version in terminal 1:

```powershell
cd raw_sql
python app.py
```

Open http://127.0.0.1:5000/. Start the ORM version in terminal 2, from the project root:

```powershell
cd orm
python app.py
```

Open http://127.0.0.1:5001/. Both versions use the **same configured database and table**, so a story created in one should appear in the other after refresh. Run only one app if you want to teach one approach at a time. To use separate data, create another database and use a separate `.env` for one app.

Optional ORM table setup: create the database in MySQL first, then run `python init_db.py` from `orm/`. It creates missing tables but **does not update existing table columns**. The supplied `schema.sql` is the simplest common starting point.

## Compare line by line

| Task | Raw SQL | ORM |
|---|---|---|
| Create | `INSERT ...`, cursor, `commit()` | `Story(...)`, `db.session.add()`, `db.session.commit()` |
| Read list | `SELECT ...`, `fetchall()` | `db.select(Story)`, `execute(...).scalars().all()` |
| Read one | parameterized `SELECT`, `fetchone()` | `db.session.get(Story, id)` |
| Update | `UPDATE ...`, cursor, `commit()` | change `story` attributes, `db.session.commit()` |
| Delete | `DELETE ...`, cursor, `commit()` | `db.session.delete(story)`, `db.session.commit()` |

## Classroom checks

1. Create a story at port 5000; refresh port 5001. Explain why it appears there.
2. Edit it at port 5001; refresh port 5000.
3. Stop and restart both apps; check the saved story again.
4. Submit a blank form and explain why no record was saved.
5. Read both `app.py` files and identify what produces the SQL in each version.

For illustration only, delete the `db.session.commit()` line in a disposable copy, restart, and try creating a story. Restore the line after the prediction exercise. The raw SQL version also needs its `db.commit()`.

**Note:** `debug=True` is for local development. These demos intentionally omit login and CSRF protection to keep the ORM comparison focused. Do not deploy them publicly as written.
