"""Regenerate schema.sql (MySQL DDL) from the ORM models: `python make_schema.py`."""
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.extensions import db
from app.models import *  # noqa: F401,F403  (registers all tables)

out = ["-- MySQL 8 schema generated from app/models.py\nCREATE DATABASE IF NOT EXISTS claims_db CHARACTER SET utf8mb4;\nUSE claims_db;\n"]
for t in db.metadata.sorted_tables:
    out.append(str(CreateTable(t).compile(dialect=mysql.dialect())).strip() + ";")
    out += [str(CreateIndex(i).compile(dialect=mysql.dialect())).strip() + ";" for i in sorted(t.indexes, key=lambda i: i.name)]
open("schema.sql", "w").write("\n\n".join(out) + "\n")
