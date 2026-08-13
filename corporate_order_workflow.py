from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import jsonify, request, session


OFFICE_TIMEZONE = ZoneInfo("America/Chicago")


def _connect(db_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def _table_columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in db.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_workflow_schema(db_path: Path) -> None:
    with _connect(db_path) as db:
        po_columns = _table_columns(db, "purchase_orders")
        if po_columns:
            if "corporate_form_generated_at" not in po_columns:
                db.execute("ALTER TABLE purchase_orders ADD COLUMN corporate_form_generated_at TEXT NOT NULL DEFAULT ''")
            if "email_sent_at" not in po_columns:
                db.execute("ALTER TABLE purchase_orders ADD COLUMN email_sent_at TEXT NOT NULL DEFAULT ''")

        line_columns = _table_columns(db, "purchase_order_lines")
        if line_columns and "order_source_key" not in line_columns:
            db.execute("ALTER TABLE purchase_order_lines ADD COLUMN order_source_key TEXT NOT NULL DEFAULT ''")
        db.commit()


def _next_po_number(db: sqlite3.Connection) -> str:
    existing = db.execute("SELECT current_value FROM app_counters WHERE name = 'po_number'").fetchone()
    if existing is None:
        row = db.execute(
            """
            SELECT MAX(CAST(SUBSTR(po_number, 4) AS INTEGER)) AS max_po_number
            FROM purchase_orders
            WHERE po_number LIKE 'PO-%'
            """
        ).fetchone()
        current = max(int(row["max_po_number"] or 1000), 1000)
        db.execute(
            "INSERT INTO app_counters (name, current_value) VALUES ('po_number', ?)",
            (current,),
        )
    else:
        current = max(int(existing["current_value"] or 1000), 1000)

    next_value = current + 1
    db.execute(
        "UPDATE app_counters SET current_value = ? WHERE name = 'po_number'",
        (next_value,),
    )
    return f"PO-{next_value}"


def _create_email_pending_purchase_orders(db_path: Path, warehouse_id: int) -> list[dict]:
    now = datetime.now(OFFICE_TIMEZONE)
    timestamp = now.isoformat()
    eta_value = (now + timedelta(days=7)).date().isoformat()
    actor_id = session.get("user_id")

    db = _connect(db_path)
    try:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute(
            """
            SELECT order_list_items.*, parts.part_number, parts.description, vendors.name AS vendor_name
            FROM order_list_items
            JOIN parts ON parts.id = order_list_items.part_id
            JOIN vendors ON vendors.id = order_list_items.vendor_id
            WHERE order_list_items.warehouse_id = ?
            ORDER BY order_list_items.id
            """,
            (warehouse_id,),
        ).fetchall()
        if not rows:
            db.rollback()
            return []

        grouped: dict[tuple[int, str], list[sqlite3.Row]] = defaultdict(list)
        for row in rows:
            grouped[(int(row["vendor_id"]), str(row["template_id"] or ""))].append(row)

        created: list[dict] = []
        for (vendor_id, template_id), items in grouped.items():
            po_number = _next_po_number(db)
            total_quantity = sum(int(item["quantity_requested"] or 0) for item in items)
            first_part_id = int(items[0]["part_id"])
            vendor_name = str(items[0]["vendor_name"] or "Corporate Purchasing")

            cursor = db.execute(
                """
                INSERT INTO purchase_orders (
                    warehouse_id, po_number, vendor_id, template_id, eta, notes, status,
                    created_at, updated_at, created_by_user_id, updated_by_user_id,
                    part_id, quantity, received_quantity, corporate_form_generated_at, email_sent_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'Email Pending', ?, ?, ?, ?, ?, ?, 0, ?, '')
                """,
                (
                    warehouse_id,
                    po_number,
                    vendor_id,
                    template_id,
                    eta_value,
                    "Corporate order form generated. Email to purchasing, then confirm Email Sent in ShopFlow.",
                    timestamp,
                    timestamp,
                    actor_id,
                    actor_id,
                    first_part_id,
                    total_quantity,
                    timestamp,
                ),
            )
            po_id = int(cursor.lastrowid)

            line_items: list[dict] = []
            for item in items:
                db.execute(
                    """
                    INSERT INTO purchase_order_lines (
                        purchase_order_id, part_id, quantity_ordered, quantity_received,
                        notes, created_at, updated_at, order_source_key
                    )
                    VALUES (?, ?, ?, 0, ?, ?, ?, ?)
                    """,
                    (
                        po_id,
                        int(item["part_id"]),
                        int(item["quantity_requested"]),
                        str(item["notes"] or ""),
                        timestamp,
                        timestamp,
                        str(item["order_source_key"] or ""),
                    ),
                )
                line_items.append(
                    {
                        "partId": int(item["part_id"]),
                        "partNumber": str(item["part_number"]),
                        "description": str(item["description"]),
                        "quantity": int(item["quantity_requested"]),
                    }
                )

            created.append(
                {
                    "id": po_id,
                    "poNumber": po_number,
                    "vendorName": vendor_name,
                    "templateId": template_id,
                    "status": "Email Pending",
                    "lineItems": line_items,
                }
            )

        # Only clear staging after every PO and line has been created successfully.
        db.execute("DELETE FROM order_list_items WHERE warehouse_id = ?", (warehouse_id,))
        db.commit()
        return created
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _find_endpoint(app, rule_text: str, method: str = "POST") -> str | None:
    for rule in app.url_map.iter_rules():
        if rule.rule == rule_text and method in rule.methods:
            return str(rule.endpoint)
    return None


def register_corporate_order_workflow(app, *, db_path: str | Path) -> None:
    """Reconnect corporate PDF generation to ShopFlow's existing PO/status workflow."""
    if app.extensions.get("shopflow_corporate_order_workflow"):
        return

    database_path = Path(db_path)
    _ensure_workflow_schema(database_path)

    generate_endpoint = _find_endpoint(app, "/api/order-forms/generate")
    if generate_endpoint and generate_endpoint in app.view_functions:
        original_generate = app.view_functions[generate_endpoint]

        @wraps(original_generate)
        def generate_with_purchase_order_workflow(*args, **kwargs):
            # First build the PDFs. If form generation fails, leave the staging list untouched.
            original_response = original_generate(*args, **kwargs)
            response = app.make_response(original_response)
            if response.status_code != 200:
                return original_response

            payload = request.get_json(silent=True) or {}
            try:
                warehouse_id = int(payload.get("warehouseId") or 0)
            except (TypeError, ValueError):
                warehouse_id = 0
            if warehouse_id <= 0:
                return jsonify({"error": "Choose a warehouse first."}), 400

            try:
                created = _create_email_pending_purchase_orders(database_path, warehouse_id)
            except sqlite3.IntegrityError:
                app.logger.exception("Corporate form workflow failed while creating purchase orders.")
                return jsonify({"error": "The forms were prepared, but the purchase-order records could not be created. Nothing was cleared; try generating again."}), 409
            except Exception:
                app.logger.exception("Corporate form workflow failed after PDF generation.")
                return jsonify({"error": "The forms were prepared, but ShopFlow could not finish the ordering workflow. The staging list was kept so you can safely try again."}), 500

            if not created:
                return jsonify({"error": "No staged items were available to create purchase orders."}), 409

            response.headers["X-Created-Purchase-Orders"] = str(len(created))
            response.headers["X-Order-Workflow-Status"] = "Email Pending"
            return response

        app.view_functions[generate_endpoint] = generate_with_purchase_order_workflow

    # Preserve the old Email Sent button/status route, while recording when that
    # confirmation occurred for an audit trail.
    status_endpoint = _find_endpoint(app, "/api/purchase-orders/<int:po_id>/status")
    if status_endpoint and status_endpoint in app.view_functions:
        original_status = app.view_functions[status_endpoint]

        @wraps(original_status)
        def status_with_email_timestamp(po_id: int, *args, **kwargs):
            payload = request.get_json(silent=True) or {}
            requested_status = str(payload.get("status") or "").strip()
            original_response = original_status(po_id, *args, **kwargs)
            response = app.make_response(original_response)
            if response.status_code == 200 and requested_status == "Waiting for Part":
                now = datetime.now(OFFICE_TIMEZONE).isoformat()
                with _connect(database_path) as db:
                    db.execute(
                        "UPDATE purchase_orders SET email_sent_at = CASE WHEN TRIM(email_sent_at) = '' THEN ? ELSE email_sent_at END WHERE id = ?",
                        (now, po_id),
                    )
                    db.commit()
            return original_response

        app.view_functions[status_endpoint] = status_with_email_timestamp

    # Load a tiny companion script that refreshes the existing Purchase Orders UI
    # after the ZIP is generated, so Email Sent appears immediately without a reload.
    @app.after_request
    def inject_corporate_workflow_ui(response):
        content_type = str(response.headers.get("Content-Type") or "")
        if response.status_code != 200 or "text/html" not in content_type.lower():
            return response
        try:
            html = response.get_data(as_text=True)
        except Exception:
            return response
        marker = "/assets/order_workflow_enhancements.js"
        if marker in html or "</body>" not in html.lower():
            return response
        index = html.lower().rfind("</body>")
        html = html[:index] + f'<script src="{marker}"></script>' + html[index:]
        response.set_data(html)
        response.headers["Content-Length"] = str(len(response.get_data()))
        return response

    app.extensions["shopflow_corporate_order_workflow"] = {
        "generateEndpoint": generate_endpoint,
        "statusEndpoint": status_endpoint,
    }
