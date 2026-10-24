"""Regenerate schema.sql (MySQL tables + the one status trigger) from app.py: `python make_schema.py`."""
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

from app import MYSQL_STATUS_TRIGGER, db  # importing app.py registers every model table on db.metadata

out = ["-- MySQL 8 schema generated from the models in app.py\nCREATE DATABASE IF NOT EXISTS claims_db CHARACTER SET utf8mb4;\nUSE claims_db;\n"]
for t in db.metadata.sorted_tables:
    out.append(str(CreateTable(t).compile(dialect=mysql.dialect())).strip() + ";")
    out += [str(CreateIndex(i).compile(dialect=mysql.dialect())).strip() + ";" for i in sorted(t.indexes, key=lambda i: i.name)]
out.append("DROP TRIGGER IF EXISTS after_claim_insert;\nDROP TRIGGER IF EXISTS after_document_status_update;\n"
           "DROP TRIGGER IF EXISTS after_claim_status_update;\n"
           "DELIMITER $$\n" + MYSQL_STATUS_TRIGGER.strip() + "$$\nDELIMITER ;")   # the ONE status trigger
open("schema.sql", "w").write("\n\n".join(out) + "\n")
