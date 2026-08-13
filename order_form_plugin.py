from __future__ import annotations

import json
import re
import sqlite3
import zipfile
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Callable

import fitz
from flask import Response, jsonify, request, send_file


DEFAULT_OFFICE_NUMBER = "93"
DEFAULT_LOCATION = "Davenport"


def _normalize_part_number(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "order_form"


def _load_catalog(catalog_path: Path) -> dict:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(data.get("templates"), list) or not isinstance(data.get("sources"), list):
        raise ValueError("Order form catalog is missing templates or sources.")
    return data


def register_order_form_plugin(
    app,
    *,
    db_path: str | Path,
    base_dir: str | Path | None = None,
    permission_checker: Callable[[str], bool] | None = None,
) -> None:
    """Register corporate order-form mapping, staging, and PDF generation routes."""
    if app.extensions.get("shopflow_order_form_plugin"):
        return

    root = Path(base_dir or Path(__file__).resolve().parent)
    order_forms_dir = root / "order_forms"
    catalog_path = order_forms_dir / "order_form_catalog.json"
    catalog = _load_catalog(catalog_path)
    office_number = str(catalog.get("office_number") or DEFAULT_OFFICE_NUMBER)
    location = str(catalog.get("location") or DEFAULT_LOCATION)
    database_path = Path(db_path)

    templates_by_id = {
        str(template["template_id"]): template
        for template in catalog["templates"]
        if template.get("active_for_ordering", True)
    }
    sources_by_key: dict[str, dict] = {}
    sources_by_part: dict[str, list[dict]] = {}
    for source in catalog["sources"]:
        template_id = str(source.get("template_id") or "")
        if template_id not in templates_by_id:
            continue
        source_key = str(source.get("source_key") or "")
        if not source_key:
            continue
        sources_by_key[source_key] = source
        part_key = _normalize_part_number(source.get("part_number"))
        if part_key:
            sources_by_part.setdefault(part_key, []).append(source)

    def connect_db() -> sqlite3.Connection:
        db = sqlite3.connect(database_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def can_purchase() -> bool:
        if permission_checker is None:
            return True
        try:
            return bool(permission_checker("purchase_orders_access"))
        except Exception:
            return False

    def ensure_schema() -> None:
        with connect_db() as db:
            existing = {row["name"] for row in db.execute("PRAGMA table_info(order_list_items)")}
            if not existing:
                return
            if "order_source_key" not in existing:
                db.execute("ALTER TABLE order_list_items ADD COLUMN order_source_key TEXT NOT NULL DEFAULT ''")
            if "restriction_acknowledged_at" not in existing:
                db.execute(
                    "ALTER TABLE order_list_items ADD COLUMN restriction_acknowledged_at TEXT NOT NULL DEFAULT ''"
                )
            db.commit()

    ensure_schema()

    def ensure_template(db: sqlite3.Connection, source: dict) -> str:
        template_id = str(source["template_id"])
        template = templates_by_id[template_id]
        existing = db.execute(
            "SELECT template_id FROM order_form_templates WHERE template_id = ?", (template_id,)
        ).fetchone()
        now = datetime.now().isoformat()
        notes = f"Corporate PDF template: {template['file_name']}"
        if existing is None:
            db.execute(
                """
                INSERT INTO order_form_templates (template_id, name, form_variant, notes, created_at, updated_at)
                VALUES (?, ?, 'corporate_pdf', ?, ?, ?)
                """,
                (template_id, str(template["template_name"]), notes, now, now),
            )
        else:
            db.execute(
                """
                UPDATE order_form_templates
                SET name = ?, form_variant = 'corporate_pdf', notes = ?, updated_at = ?
                WHERE template_id = ?
                """,
                (str(template["template_name"]), notes, now, template_id),
            )
        return template_id

    def ensure_vendor(db: sqlite3.Connection, source: dict) -> int:
        vendor_name = str(source.get("vendor") or "Corporate Purchasing").strip() or "Corporate Purchasing"
        template_id = str(source["template_id"])
        row = db.execute(
            "SELECT id, linked_template_id FROM vendors WHERE LOWER(name) = LOWER(?) ORDER BY id LIMIT 1",
            (vendor_name,),
        ).fetchone()
        if row is not None:
            if not str(row["linked_template_id"] or "").strip():
                db.execute("UPDATE vendors SET linked_template_id = ? WHERE id = ?", (template_id, int(row["id"])))
            return int(row["id"])
        cursor = db.execute(
            """
            INSERT INTO vendors (name, contact, email, phone, lead_time_days, linked_template_id)
            VALUES (?, '', '', '', 0, ?)
            """,
            (vendor_name, template_id),
        )
        return int(cursor.lastrowid)

    def serialize_source(source: dict, *, default_vendor_name: str = "") -> dict:
        restrictions = [str(item) for item in source.get("restrictions", []) if str(item).strip()]
        return {
            "sourceKey": str(source["source_key"]),
            "templateId": str(source["template_id"]),
            "templateName": str(source.get("template_name") or "Order Form"),
            "fileName": str(source.get("file_name") or ""),
            "page": int(source.get("page") or 1),
            "vendor": str(source.get("vendor") or "Corporate Purchasing"),
            "vendorItemNumber": str(source.get("vendor_item_number") or ""),
            "packCount": str(source.get("pack_count") or ""),
            "requestPer": str(source.get("request_per") or ""),
            "restrictions": restrictions,
            "requiresAcknowledgement": bool(restrictions),
            "matchesCurrentVendor": bool(
                default_vendor_name
                and str(source.get("vendor") or "").strip().lower() == default_vendor_name.strip().lower()
            ),
        }

    @app.get("/api/order-form-config")
    def order_form_config():
        if not can_purchase():
            return jsonify({"error": "Purchase-order access required."}), 403
        return jsonify(
            {
                "officeNumber": office_number,
                "location": location,
                "templateCount": len(templates_by_id),
                "mappedSourceCount": len(sources_by_key),
                "mappedPartCount": len(sources_by_part),
            }
        )

    @app.get("/api/order-sources/<int:part_id>")
    def order_sources_for_part(part_id: int):
        if not can_purchase():
            return jsonify({"error": "Purchase-order access required."}), 403
        with connect_db() as db:
            part = db.execute(
                """
                SELECT parts.*, vendors.name AS current_vendor_name
                FROM parts
                LEFT JOIN vendors ON vendors.id = parts.vendor_id
                WHERE parts.id = ?
                """,
                (part_id,),
            ).fetchone()
            if part is None:
                return jsonify({"error": "Part not found."}), 404
            part_key = _normalize_part_number(part["part_number"])
            options = list(sources_by_part.get(part_key, []))
            options.sort(
                key=lambda source: (
                    0
                    if str(source.get("vendor") or "").strip().lower()
                    == str(part["current_vendor_name"] or "").strip().lower()
                    else 1,
                    str(source.get("vendor") or ""),
                    str(source.get("template_name") or ""),
                )
            )
            suggested = 1
            if str(part["item_type"] or "stocked") != "non_stock":
                suggested = max(int(part["reorder_point"] or 0) * 2 - int(part["stock"] or 0), 1)
            return jsonify(
                {
                    "officeNumber": office_number,
                    "location": location,
                    "part": {
                        "id": int(part["id"]),
                        "partNumber": str(part["part_number"]),
                        "description": str(part["description"]),
                        "stock": int(part["stock"] or 0),
                        "reorderPoint": int(part["reorder_point"] or 0),
                        "itemType": str(part["item_type"] or "stocked"),
                        "currentVendor": str(part["current_vendor_name"] or ""),
                    },
                    "suggestedQuantity": suggested,
                    "sources": [
                        serialize_source(source, default_vendor_name=str(part["current_vendor_name"] or ""))
                        for source in options
                    ],
                }
            )

    @app.post("/api/order-list-v2")
    def stage_order_list_v2():
        if not can_purchase():
            return jsonify({"error": "Purchase-order access required."}), 403
        payload = request.get_json(force=True) or {}
        try:
            warehouse_id = int(payload.get("warehouseId") or 0)
            part_id = int(payload.get("partId") or 0)
            quantity = int(payload.get("quantity") or 0)
        except (TypeError, ValueError):
            return jsonify({"error": "Warehouse, part, and quantity must be valid numbers."}), 400
        source_key = str(payload.get("sourceKey") or "").strip()
        acknowledged = bool(payload.get("acknowledgedRestrictions"))
        notes = str(payload.get("notes") or "").strip()
        if warehouse_id <= 0 or part_id <= 0 or quantity <= 0:
            return jsonify({"error": "Choose a warehouse, part, and quantity greater than zero."}), 400
        source = sources_by_key.get(source_key)
        if source is None:
            return jsonify({"error": "Choose a valid corporate ordering source for this item."}), 400
        restrictions = [str(item) for item in source.get("restrictions", []) if str(item).strip()]
        if restrictions and not acknowledged:
            return jsonify({"error": "Acknowledge the ordering restrictions before continuing.", "restrictions": restrictions}), 409

        with connect_db() as db:
            part = db.execute(
                "SELECT * FROM parts WHERE id = ? AND warehouse_id = ?", (part_id, warehouse_id)
            ).fetchone()
            if part is None:
                return jsonify({"error": "Part not found in the selected warehouse."}), 404
            if _normalize_part_number(part["part_number"]) != _normalize_part_number(source.get("part_number")):
                return jsonify({"error": "That ordering source does not belong to this part."}), 400
            template_id = ensure_template(db, source)
            vendor_id = ensure_vendor(db, source)
            now = datetime.now().isoformat()
            acknowledged_at = now if restrictions and acknowledged else ""
            existing = db.execute(
                "SELECT id FROM order_list_items WHERE warehouse_id = ? AND part_id = ? ORDER BY id LIMIT 1",
                (warehouse_id, part_id),
            ).fetchone()
            if existing is None:
                cursor = db.execute(
                    """
                    INSERT INTO order_list_items (
                        warehouse_id, part_id, vendor_id, template_id, quantity_requested, notes,
                        created_at, updated_at, order_source_key, restriction_acknowledged_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        warehouse_id,
                        part_id,
                        vendor_id,
                        template_id,
                        quantity,
                        notes,
                        now,
                        now,
                        source_key,
                        acknowledged_at,
                    ),
                )
                item_id = int(cursor.lastrowid)
            else:
                item_id = int(existing["id"])
                db.execute(
                    """
                    UPDATE order_list_items
                    SET vendor_id = ?, template_id = ?, quantity_requested = ?, notes = ?, updated_at = ?,
                        order_source_key = ?, restriction_acknowledged_at = ?
                    WHERE id = ?
                    """,
                    (
                        vendor_id,
                        template_id,
                        quantity,
                        notes,
                        now,
                        source_key,
                        acknowledged_at,
                        item_id,
                    ),
                )
            db.commit()
            return jsonify(
                {
                    "ok": True,
                    "itemId": item_id,
                    "partNumber": str(part["part_number"]),
                    "vendor": str(source.get("vendor") or "Corporate Purchasing"),
                    "templateName": str(source.get("template_name") or "Order Form"),
                }
            )

    def stamp_centered(page: fitz.Page, box: list[float] | None, text: str, fontsize: float = 10.0) -> None:
        if not box or not text:
            return
        rect = fitz.Rect(*[float(value) for value in box])
        rect = fitz.Rect(rect.x0 + 1.5, rect.y0 + 1.5, rect.x1 - 1.5, rect.y1 - 1.5)
        page.insert_textbox(rect, str(text), fontsize=fontsize, fontname="helv", align=fitz.TEXT_ALIGN_CENTER)

    def fill_template(template: dict, requested_sources: list[tuple[dict, int]]) -> bytes:
        source_pdf = order_forms_dir / str(template["file_name"])
        if not source_pdf.exists():
            raise FileNotFoundError(f"Missing corporate order form: {source_pdf.name}")
        document = fitz.open(source_pdf)
        today_text = date.today().strftime("%m/%d/%Y")
        page_metadata = {int(item["page"]): item for item in template.get("pages", [])}
        for page_number, page in enumerate(document, start=1):
            metadata = page_metadata.get(page_number, {})
            stamp_centered(page, metadata.get("date_box"), today_text, fontsize=9.5)
            stamp_centered(page, metadata.get("office_box"), office_number, fontsize=10.0)

        totals: dict[tuple[int, tuple[float, ...]], int] = {}
        for source, quantity in requested_sources:
            page_number = int(source.get("page") or 1)
            box = tuple(float(value) for value in source.get("request_box", []))
            if len(box) != 4:
                continue
            key = (page_number, box)
            totals[key] = totals.get(key, 0) + int(quantity)
        for (page_number, box), quantity in totals.items():
            if page_number < 1 or page_number > document.page_count:
                continue
            stamp_centered(document[page_number - 1], list(box), str(quantity), fontsize=10.5)

        output = BytesIO()
        document.save(output, garbage=4, deflate=True)
        document.close()
        return output.getvalue()

    @app.post("/api/order-forms/generate")
    def generate_corporate_order_forms():
        if not can_purchase():
            return jsonify({"error": "Purchase-order access required."}), 403
        payload = request.get_json(silent=True) or {}
        try:
            warehouse_id = int(payload.get("warehouseId") or 0)
        except (TypeError, ValueError):
            warehouse_id = 0
        if warehouse_id <= 0:
            return jsonify({"error": "Choose a warehouse first."}), 400

        with connect_db() as db:
            rows = db.execute(
                """
                SELECT order_list_items.*, parts.part_number, parts.description
                FROM order_list_items
                JOIN parts ON parts.id = order_list_items.part_id
                WHERE order_list_items.warehouse_id = ?
                ORDER BY order_list_items.id
                """,
                (warehouse_id,),
            ).fetchall()
        if not rows:
            return jsonify({"error": "The order list is empty."}), 400

        grouped: dict[str, list[tuple[dict, int]]] = {}
        unmapped: list[str] = []
        for row in rows:
            source_key = str(row["order_source_key"] or "").strip()
            source = sources_by_key.get(source_key)
            if source is None:
                unmapped.append(str(row["part_number"]))
                continue
            restrictions = [str(item) for item in source.get("restrictions", []) if str(item).strip()]
            if restrictions and not str(row["restriction_acknowledged_at"] or "").strip():
                return jsonify(
                    {
                        "error": f"{row['part_number']} has ordering restrictions that still need acknowledgement.",
                        "restrictions": restrictions,
                    }
                ), 409
            grouped.setdefault(str(source["template_id"]), []).append((source, int(row["quantity_requested"])))

        if unmapped:
            return jsonify(
                {
                    "error": "Some staged items were added before corporate form mapping was selected. Re-add these items before generating forms.",
                    "unmappedParts": unmapped,
                }
            ), 409
        if not grouped:
            return jsonify({"error": "No mapped corporate forms were found for the staged items."}), 400

        zip_buffer = BytesIO()
        generated_names: list[str] = []
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for template_id, requested_sources in sorted(grouped.items()):
                template = templates_by_id.get(template_id)
                if template is None:
                    continue
                filled_pdf = fill_template(template, requested_sources)
                base = Path(str(template["file_name"])).stem
                filename = f"Office_{office_number}_{_safe_filename(base)}_{date.today().isoformat()}.pdf"
                archive.writestr(filename, filled_pdf)
                generated_names.append(filename)
            archive.writestr(
                "README.txt",
                "Generated by ShopFlow for Office "
                + office_number
                + " - "
                + location
                + "\nDate: "
                + date.today().strftime("%m/%d/%Y")
                + "\n\nFiles:\n- "
                + "\n- ".join(generated_names),
            )
        zip_buffer.seek(0)
        response = send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"Office_{office_number}_Order_Forms_{date.today().isoformat()}.zip",
        )
        response.headers["X-Generated-Forms"] = str(len(generated_names))
        return response

    @app.after_request
    def inject_order_form_ui(response: Response):
        content_type = str(response.headers.get("Content-Type") or "")
        if response.status_code != 200 or "text/html" not in content_type.lower():
            return response
        try:
            html = response.get_data(as_text=True)
        except Exception:
            return response
        marker = "/assets/order_form_enhancements.js"
        if marker in html or "</body>" not in html.lower():
            return response
        script = f'<script src="{marker}"></script>'
        index = html.lower().rfind("</body>")
        html = html[:index] + script + html[index:]
        response.set_data(html)
        response.headers["Content-Length"] = str(len(response.get_data()))
        return response

    app.extensions["shopflow_order_form_plugin"] = {
        "office_number": office_number,
        "location": location,
        "catalog_path": str(catalog_path),
        "mapped_source_count": len(sources_by_key),
    }
