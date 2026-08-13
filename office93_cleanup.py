from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import jsonify


CLEANUP_MARKER = "office93_demo_cleanup_v1"
KEEP_USERNAME = "manager"

TRANSACTION_TABLES = [
    "job_notes",
    "job_attachments",
    "job_part_requirements",
    "usage_logs",
    "receiving_logs",
    "purchase_order_lines",
    "order_list_items",
    "reorder_requests",
    "stock_transfers",
    "jobs",
    "purchase_orders",
]


def _table_exists(db: sqlite3.Connection, table: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone() is not None


def _wipe_table(db: sqlite3.Connection, table: str) -> int:
    if not _table_exists(db, table):
        return 0
    before = int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    db.execute(f"DELETE FROM {table}")
    return before


def cleanup_demo_seed_data(db_path: str | Path, *, force: bool = False) -> dict:
    database_path = Path(db_path)
    db = sqlite3.connect(database_path)
    db.row_factory = sqlite3.Row
    try:
        db.execute(
            "CREATE TABLE IF NOT EXISTS app_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '')"
        )
        marker = db.execute("SELECT value FROM app_metadata WHERE key = ?", (CLEANUP_MARKER,)).fetchone()
        if marker is not None and not force:
            return {"cleaned": False, "alreadyCleaned": True}

        # This cleanup intentionally removes every old demo transaction before the
        # Office 93 catalog is rebuilt. No live Office 93 operational data exists yet.
        db.execute("PRAGMA foreign_keys = OFF")
        removed: dict[str, int] = {}

        for table in TRANSACTION_TABLES:
            removed[table] = _wipe_table(db, table)

        removed["parts"] = _wipe_table(db, "parts")
        removed["warehouses"] = _wipe_table(db, "warehouses")
        removed["vendors"] = _wipe_table(db, "vendors")
        removed["order_form_templates"] = _wipe_table(db, "order_form_templates")

        # Keep the one login currently needed to administer the pilot. Remove the
        # Dallas/Chicago/Phoenix seeded users and any other generated test accounts.
        if _table_exists(db, "users"):
            removed["users"] = int(
                db.execute("SELECT COUNT(*) FROM users WHERE username <> ?", (KEEP_USERNAME,)).fetchone()[0]
            )
            db.execute("DELETE FROM users WHERE username <> ?", (KEEP_USERNAME,))

        # Reset the PO sequence so the first real PO does not inherit test numbering.
        if _table_exists(db, "app_counters"):
            db.execute("DELETE FROM app_counters WHERE name = 'po_number'")

        # Reset autoincrement sequences for data tables we just cleared. This is not
        # required for correctness, but it keeps the pilot database clean and readable.
        if _table_exists(db, "sqlite_sequence"):
            cleared_tables = TRANSACTION_TABLES + ["parts", "warehouses", "vendors", "order_form_templates"]
            placeholders = ",".join("?" for _ in cleared_tables)
            db.execute(f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})", cleared_tables)

        db.execute(
            "INSERT OR REPLACE INTO app_metadata (key, value) VALUES (?, '1')",
            (CLEANUP_MARKER,),
        )
        db.commit()
        return {"cleaned": True, "alreadyCleaned": False, "removed": removed}
    finally:
        db.close()


def disable_demo_reset(app) -> None:
    # app.py still contains the historical /api/reset route. Replace its handler at
    # runtime so the old Reset Demo Data control cannot repopulate fake records.
    if "api_reset" not in app.view_functions:
        return

    def demo_reset_disabled():
        return jsonify({"error": "Demo reset has been disabled for the Office 93 pilot."}), 410

    app.view_functions["api_reset"] = demo_reset_disabled
