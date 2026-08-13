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

        # This conversion intentionally removes the old demo/test database before
        # Office 93 is rebuilt. It runs once, before any real pilot counts are entered.
        db.execute("PRAGMA foreign_keys = OFF")
        removed: dict[str, int] = {}

        for table in TRANSACTION_TABLES:
            removed[table] = _wipe_table(db, table)

        removed["parts"] = _wipe_table(db, "parts")
        removed["warehouses"] = _wipe_table(db, "warehouses")
        removed["vendors"] = _wipe_table(db, "vendors")
        removed["order_form_templates"] = _wipe_table(db, "order_form_templates")

        # Keep the one login needed to administer the pilot. Everything else in the
        # current database was generated for Dallas/Chicago/Phoenix testing.
        if _table_exists(db, "users"):
            removed["users"] = int(
                db.execute("SELECT COUNT(*) FROM users WHERE username <> ?", (KEEP_USERNAME,)).fetchone()[0]
            )
            db.execute("DELETE FROM users WHERE username <> ?", (KEEP_USERNAME,))

        # Start real PO numbering from the original clean baseline rather than from
        # whatever number the stress/demo runs happened to reach.
        if _table_exists(db, "app_counters"):
            db.execute(
                "INSERT OR REPLACE INTO app_counters (name, current_value) VALUES ('po_number', 1000)"
            )

        # Reset autoincrement sequences for the cleared operational tables. This is
        # cosmetic, but keeps the pilot database much easier to inspect and support.
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
    # app.py still contains the historical /api/reset route. Replace its handler so
    # an old bookmark or stale browser cannot repopulate fake records.
    if "api_reset" in app.view_functions:
        def demo_reset_disabled():
            return jsonify({"error": "Demo reset has been disabled for the Office 93 pilot."}), 410

        app.view_functions["api_reset"] = demo_reset_disabled

    # Also remove the obsolete Reset Demo Data button from the rendered pilot UI.
    @app.after_request
    def remove_demo_reset_button(response):
        content_type = str(response.headers.get("Content-Type") or "")
        if response.status_code != 200 or "text/html" not in content_type.lower():
            return response
        try:
            html = response.get_data(as_text=True)
        except Exception:
            return response
        if "Reset Demo Data" not in html or "</body>" not in html.lower():
            return response
        script = """
<script>
(() => {
  const removeDemoReset = () => {
    document.querySelectorAll('button').forEach((button) => {
      if ((button.textContent || '').trim() === 'Reset Demo Data') button.remove();
    });
  };
  removeDemoReset();
  new MutationObserver(removeDemoReset).observe(document.documentElement, {childList:true, subtree:true});
})();
</script>
"""
        index = html.lower().rfind("</body>")
        html = html[:index] + script + html[index:]
        response.set_data(html)
        response.headers["Content-Length"] = str(len(response.get_data()))
        return response
