from __future__ import annotations

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

FORM_META = {
    "1st Aid Order Form.pdf": ("first-aid", "First Aid Order Form", "Corporate Purchasing", True),
    "84 Lumber.pdf": ("84-lumber", "84 Lumber Order Form", "84 Lumber", True),
    "Advantage-Makita.pdf": ("advantage-makita", "Advantage / Makita Order Form", "Advantage / Scott Electric", True),
    "Alumax.pdf": ("alumax", "Alumax Order Form", "Alumax", True),
    "Amazon.pdf": ("amazon", "Amazon Order Form", "Amazon", True),
    "BF Walls & Accessories (1).pdf": ("bf-walls", "BF Walls & Accessories Order Form", "Bath Fitter Corporate", True),
    "Basco.pdf": ("basco", "Basco Order Form", "Basco", True),
    "Facilities and Warehouse Supplies.pdf": ("facilities", "Facilities Supplies Order Form", "Corporate Purchasing", True),
    "Ferguson.pdf": ("ferguson", "Ferguson Order Form", "Ferguson", True),
    "Fleet.pdf": ("fleet", "Fleet Order Form", "Corporate Purchasing", True),
    "Grainger.pdf": ("grainger", "Grainger Order Form", "Grainger", True),
    "Home Depot Lumber.pdf": ("home-depot", "Home Depot Order Form", "Home Depot", True),
    "Lowe's Tools and Lumber.pdf": ("lowes", "Lowe's Order Form", "Lowe's", True),
    # Kept for reference/testing, but Davenport is using Lowe's/HD/84 as separate forms for now.
    "Lumber Order Sheet Test.pdf": ("lumber-combined", "Lumber Order Form", "Lumber Vendor Choice", False),
    "MSC.pdf": ("msc", "MSC Order Form", "MSC", True),
    "PPE Order Form.pdf": ("ppe", "PPE Order Form", "Corporate Purchasing", True),
    "RF Fager (1).pdf": ("rf-fager", "RF Fager Order Form", "RF Fager", True),
    "Sales Kit-Corp Order Only.pdf": ("sales-kit", "Sales Supply Order Form", "Bath Fitter Corporate", True),
    "Seachrome (1).pdf": ("seachrome", "SeaChrome Order Form", "SeaChrome", True),
    "TB Philly.pdf": ("tb-philly", "TB Philly Order Form", "TB Philly", True),
    "Van Supplies.pdf": ("van-supplies", "Van Supplies Order Form", "Corporate Purchasing", True),
    "Zoe.pdf": ("zoe", "Zoe Order Form", "Zoe", True),
}

FORM_WARNINGS = {
    "84-lumber": ["84 Lumber form excludes IBS."],
    "advantage-makita": ["Internal transfer from Corporate is required for this form."],
    "alumax": ["Alumax has a $750 shipping minimum."],
    "bf-walls": ["Use this form for items not ordered straight to the job."],
    "basco": ["Place on office order day.", "Basco has a $750 shipping minimum."],
    "fleet": ["Code Fleet orders to 655-4135.", "Fleet form is for one each per van or warehouse supply."],
    "ppe": ["Internal transfer from Corporate is required for this form."],
    "sales-kit": ["Corporate order only."],
    "seachrome": ["SeaChrome has a $1,500 minimum order for shipping."],
    "tb-philly": ["TB Philly has a $2,500 minimum order for shipping."],
    "zoe": ["Zoe form is for service items only."],
}

ALIASES = [
    (re.compile(r"\bRF\s*Fager\b", re.I), "RF Fager"),
    (re.compile(r"\bGrainger\b", re.I), "Grainger"),
    (re.compile(r"\bMSC\b", re.I), "MSC"),
    (re.compile(r"\bUline\b", re.I), "Uline"),
    (re.compile(r"\bAMZN\b|\bAmazon\b", re.I), "Amazon"),
    (re.compile(r"\bHome\s*Depot\b|\bHD\b", re.I), "Home Depot"),
    (re.compile(r"\bLowe'?s\b|\bLowes\b", re.I), "Lowe's"),
    (re.compile(r"\bAce\s*(?:Hdwr|Hardware)?\b", re.I), "ACE Hardware"),
    (re.compile(r"\bFerguson\b|\bFerg\.?\b", re.I), "Ferguson"),
    (re.compile(r"\bAdvantage\b", re.I), "Advantage / Scott Electric"),
    (re.compile(r"\bBath\s*Fitter\b|\bBF\b", re.I), "Bath Fitter Corporate"),
    (re.compile(r"\bWingits\b", re.I), "Wingits"),
]


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_part_number(value: object) -> str:
    return _clean(value).upper()


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "order_form"


def _infer_vendor(raw: object, default: str) -> str:
    text = _clean(raw)
    for pattern, name in ALIASES:
        if pattern.search(text):
            return name
    if text.lower().startswith("jason to order"):
        return "Corporate Purchasing"
    return default


def _row_restrictions(text: object) -> list[str]:
    raw = _clean(text)
    low = raw.lower()
    warnings: list[str] = []
    if "corp transfer" in low or "corporate transfer" in low or "sent from corporate only" in low:
        warnings.append("Corporate transfer only.")
    if "service item" in low or "services only" in low or "svc item" in low:
        warnings.append("Service item only.")
    office_match = re.search(r"offices?\s+([0-9,\sand]+)\s+only", raw, re.I)
    if office_match:
        warnings.append(f"Restricted to offices {_clean(office_match.group(1))} only.")
    if "pickup only" in low:
        warnings.append("Pickup only.")
    if "order through wingits" in low:
        warnings.append("Order through Wingits.")
    if "backup only" in low or "back-up" in low or "backup." in low:
        warnings.append("Backup source/item only.")
    multiple = re.search(r"(?:multiples? of|qty'?s of|order qty\s*)(\d+)", raw, re.I)
    if multiple:
        warnings.append(f"Order in multiples of {multiple.group(1)}.")
    multiple = re.search(r"\bOM\s*(\d+)\s*/?per", raw, re.I)
    if multiple and f"Order in multiples of {multiple.group(1)}." not in warnings:
        warnings.append(f"Order in multiples of {multiple.group(1)}.")
    return warnings


def _find_label_box(page: fitz.Page, label: str) -> list[float] | None:
    hits = page.search_for(label)
    if not hits:
        return None
    rect = hits[0]
    if label.lower().startswith("date"):
        return [round(rect.x1 + 4, 2), round(rect.y0 - 2, 2), round(min(rect.x1 + 110, page.rect.width - 12), 2), round(rect.y1 + 6, 2)]
    return [round(rect.x1 + 5, 2), round(rect.y0 - 2, 2), round(min(rect.x1 + 85, page.rect.width - 12), 2), round(rect.y1 + 6, 2)]


def _column_config(filename: str, page_number: int) -> dict[str, int | None]:
    if filename == "84 Lumber.pdf":
        return {"part": 2, "vendor_item": 0, "description": 1, "pack": None, "request_per": None, "requested": 3, "vendor": None, "header_rows": 0}
    if filename == "Sales Kit-Corp Order Only.pdf":
        return {"part": 1, "vendor_item": 1, "description": 0, "pack": None, "request_per": None, "requested": 2, "vendor": 3, "header_rows": 0}
    if filename == "BF Walls & Accessories (1).pdf":
        return {"part": 3, "vendor_item": 3, "description": 0, "pack": 1, "request_per": 2, "requested": 4, "vendor": None, "header_rows": 1}
    if filename in {"Home Depot Lumber.pdf", "Lowe's Tools and Lumber.pdf"}:
        return {"part": 2, "vendor_item": 0, "description": 1, "pack": None, "request_per": None, "requested": 3, "vendor": None, "header_rows": 1 if page_number == 1 else 0}
    return {"part": 4, "vendor_item": 0, "description": 1, "pack": 2, "request_per": 3, "requested": 5, "vendor": None, "header_rows": 1}


def _part_candidates(part_raw: object, vendor_item: object) -> list[str]:
    raw = _clean(part_raw) or _clean(vendor_item)
    if not raw:
        return []
    if raw.lower() in {"requested", "internal item#", "internal item #", "item#", "item #", "order qty", "amount"}:
        return []
    candidates: list[str] = []
    for line in re.split(r"[\n\r]+", raw):
        line = _clean(line)
        if line and len(line) <= 64:
            candidates.append(line)
    if not candidates:
        candidates = [raw]
    output: list[str] = []
    for candidate in candidates:
        match = re.search(r"#\s*([A-Z0-9][A-Z0-9_.\-/]+)", candidate, re.I)
        cleaned = _clean(match.group(1) if match else candidate)
        if cleaned and cleaned not in output:
            output.append(cleaned)
    return output


def register_order_form_plugin(
    app,
    *,
    db_path: str | Path,
    base_dir: str | Path | None = None,
    permission_checker: Callable[[str], bool] | None = None,
) -> None:
    """Register corporate order-form source selection and original-PDF stamping."""
    if app.extensions.get("shopflow_order_form_plugin"):
        return

    root = Path(base_dir or Path(__file__).resolve().parent)
    order_forms_dir = root / "order_forms"
    database_path = Path(db_path)
    source_cache: dict[str, list[dict]] = {}

    active_templates = {
        meta[0]: {"template_id": meta[0], "template_name": meta[1], "file_name": filename, "default_vendor": meta[2]}
        for filename, meta in FORM_META.items()
        if meta[3]
    }

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
            columns = {row["name"] for row in db.execute("PRAGMA table_info(order_list_items)")}
            if not columns:
                return
            if "order_source_key" not in columns:
                db.execute("ALTER TABLE order_list_items ADD COLUMN order_source_key TEXT NOT NULL DEFAULT ''")
            if "restriction_acknowledged_at" not in columns:
                db.execute("ALTER TABLE order_list_items ADD COLUMN restriction_acknowledged_at TEXT NOT NULL DEFAULT ''")
            db.commit()

    def discover_sources(part_number: str) -> list[dict]:
        part_key = _normalize_part_number(part_number)
        if part_key in source_cache:
            return [dict(item) for item in source_cache[part_key]]
        found: list[dict] = []
        for filename, meta in FORM_META.items():
            template_id, template_name, default_vendor, active = meta
            if not active:
                continue
            pdf_path = order_forms_dir / filename
            if not pdf_path.exists():
                continue
            document = fitz.open(pdf_path)
            try:
                for page_index, page in enumerate(document):
                    if not page.search_for(part_number):
                        continue
                    tables = page.find_tables().tables
                    if not tables:
                        continue
                    table = max(tables, key=lambda item: item.row_count * item.col_count)
                    rows = table.extract()
                    config = _column_config(filename, page_index + 1)
                    for row_index, row in enumerate(rows):
                        if row_index < int(config["header_rows"] or 0):
                            continue
                        values = list(row) + [None] * max(table.col_count - len(row), 0)
                        part_raw = values[int(config["part"])] if config["part"] is not None and int(config["part"]) < len(values) else ""
                        vendor_item = _clean(values[int(config["vendor_item"])]) if config["vendor_item"] is not None and int(config["vendor_item"]) < len(values) else ""
                        candidates = _part_candidates(part_raw, vendor_item)
                        if part_key not in {_normalize_part_number(candidate) for candidate in candidates}:
                            continue
                        requested_index = int(config["requested"])
                        request_box = table.rows[row_index].cells[requested_index] if requested_index < len(table.rows[row_index].cells) else None
                        if request_box is None:
                            continue
                        description = _clean(values[int(config["description"])]) if config["description"] is not None else ""
                        pack = _clean(values[int(config["pack"])]) if config["pack"] is not None and int(config["pack"]) < len(values) else ""
                        request_per = _clean(values[int(config["request_per"])]) if config["request_per"] is not None and int(config["request_per"]) < len(values) else ""
                        vendor_raw = _clean(values[int(config["vendor"])]) if config["vendor"] is not None and int(config["vendor"]) < len(values) else vendor_item
                        restrictions = list(FORM_WARNINGS.get(template_id, []))
                        for warning in _row_restrictions(" | ".join(_clean(value) for value in values if value)):
                            if warning not in restrictions:
                                restrictions.append(warning)
                        vendor = _infer_vendor(vendor_raw, default_vendor)
                        source_key = f"{template_id}|p{page_index + 1}|r{row_index}|{part_key}"
                        found.append({
                            "source_key": source_key,
                            "template_id": template_id,
                            "template_name": template_name,
                            "file_name": filename,
                            "page": page_index + 1,
                            "row_index": row_index,
                            "part_number": part_number,
                            "description": description,
                            "vendor": vendor,
                            "vendor_item_number": vendor_item,
                            "pack_count": pack,
                            "request_per": request_per,
                            "request_box": [round(float(value), 2) for value in request_box],
                            "date_box": _find_label_box(page, "Date:"),
                            "office_box": _find_label_box(page, "Office #") or _find_label_box(page, "Office"),
                            "restrictions": restrictions,
                        })
            finally:
                document.close()
        unique = {source["source_key"]: source for source in found}
        source_cache[part_key] = list(unique.values())
        return [dict(item) for item in source_cache[part_key]]

    def resolve_source(source_key: str, part_number: str) -> dict | None:
        return next((source for source in discover_sources(part_number) if source["source_key"] == source_key), None)

    ensure_schema()

    def ensure_template(db: sqlite3.Connection, source: dict) -> str:
        template_id = str(source["template_id"])
        existing = db.execute("SELECT template_id FROM order_form_templates WHERE template_id = ?", (template_id,)).fetchone()
        now = datetime.now().isoformat()
        notes = f"Corporate PDF template: {source['file_name']}"
        if existing is None:
            db.execute("INSERT INTO order_form_templates (template_id, name, form_variant, notes, created_at, updated_at) VALUES (?, ?, 'corporate_pdf', ?, ?, ?)", (template_id, str(source["template_name"]), notes, now, now))
        else:
            db.execute("UPDATE order_form_templates SET name = ?, form_variant = 'corporate_pdf', notes = ?, updated_at = ? WHERE template_id = ?", (str(source["template_name"]), notes, now, template_id))
        return template_id

    def ensure_vendor(db: sqlite3.Connection, source: dict) -> int:
        vendor_name = str(source.get("vendor") or "Corporate Purchasing").strip() or "Corporate Purchasing"
        template_id = str(source["template_id"])
        row = db.execute("SELECT id, linked_template_id FROM vendors WHERE LOWER(name) = LOWER(?) ORDER BY id LIMIT 1", (vendor_name,)).fetchone()
        if row is not None:
            if not str(row["linked_template_id"] or "").strip():
                db.execute("UPDATE vendors SET linked_template_id = ? WHERE id = ?", (template_id, int(row["id"])))
            return int(row["id"])
        cursor = db.execute("INSERT INTO vendors (name, contact, email, phone, lead_time_days, linked_template_id) VALUES (?, '', '', '', 0, ?)", (vendor_name, template_id))
        return int(cursor.lastrowid)

    def serialize_source(source: dict, default_vendor_name: str = "") -> dict:
        restrictions = [str(item) for item in source.get("restrictions", []) if str(item).strip()]
        return {
            "sourceKey": str(source["source_key"]),
            "templateId": str(source["template_id"]),
            "templateName": str(source["template_name"]),
            "fileName": str(source["file_name"]),
            "page": int(source["page"]),
            "vendor": str(source["vendor"]),
            "vendorItemNumber": str(source.get("vendor_item_number") or ""),
            "packCount": str(source.get("pack_count") or ""),
            "requestPer": str(source.get("request_per") or ""),
            "restrictions": restrictions,
            "requiresAcknowledgement": bool(restrictions),
            "matchesCurrentVendor": bool(default_vendor_name and str(source["vendor"]).strip().lower() == default_vendor_name.strip().lower()),
        }

    @app.get("/api/order-form-config")
    def order_form_config():
        if not can_purchase():
            return jsonify({"error": "Purchase-order access required."}), 403
        return jsonify({"officeNumber": DEFAULT_OFFICE_NUMBER, "location": DEFAULT_LOCATION, "templateCount": len(active_templates)})

    @app.get("/api/order-sources/<int:part_id>")
    def order_sources_for_part(part_id: int):
        if not can_purchase():
            return jsonify({"error": "Purchase-order access required."}), 403
        with connect_db() as db:
            part = db.execute("SELECT parts.*, vendors.name AS current_vendor_name FROM parts LEFT JOIN vendors ON vendors.id = parts.vendor_id WHERE parts.id = ?", (part_id,)).fetchone()
            if part is None:
                return jsonify({"error": "Part not found."}), 404
            options = discover_sources(str(part["part_number"]))
            options.sort(key=lambda source: (0 if str(source["vendor"]).strip().lower() == str(part["current_vendor_name"] or "").strip().lower() else 1, str(source["vendor"]), str(source["template_name"])))
            suggested = 1 if str(part["item_type"] or "stocked") == "non_stock" else max(int(part["reorder_point"] or 0) * 2 - int(part["stock"] or 0), 1)
            return jsonify({
                "officeNumber": DEFAULT_OFFICE_NUMBER,
                "location": DEFAULT_LOCATION,
                "part": {"id": int(part["id"]), "partNumber": str(part["part_number"]), "description": str(part["description"]), "stock": int(part["stock"] or 0), "reorderPoint": int(part["reorder_point"] or 0), "itemType": str(part["item_type"] or "stocked"), "currentVendor": str(part["current_vendor_name"] or "")},
                "suggestedQuantity": suggested,
                "sources": [serialize_source(source, str(part["current_vendor_name"] or "")) for source in options],
            })

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
        with connect_db() as db:
            part = db.execute("SELECT * FROM parts WHERE id = ? AND warehouse_id = ?", (part_id, warehouse_id)).fetchone()
            if part is None:
                return jsonify({"error": "Part not found in the selected warehouse."}), 404
            source = resolve_source(source_key, str(part["part_number"]))
            if source is None:
                return jsonify({"error": "Choose a valid corporate ordering source for this item."}), 400
            restrictions = list(source.get("restrictions", []))
            if restrictions and not acknowledged:
                return jsonify({"error": "Acknowledge the ordering restrictions before continuing.", "restrictions": restrictions}), 409
            template_id = ensure_template(db, source)
            vendor_id = ensure_vendor(db, source)
            now = datetime.now().isoformat()
            acknowledged_at = now if restrictions and acknowledged else ""
            existing = db.execute("SELECT id FROM order_list_items WHERE warehouse_id = ? AND part_id = ? ORDER BY id LIMIT 1", (warehouse_id, part_id)).fetchone()
            if existing is None:
                cursor = db.execute("INSERT INTO order_list_items (warehouse_id, part_id, vendor_id, template_id, quantity_requested, notes, created_at, updated_at, order_source_key, restriction_acknowledged_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (warehouse_id, part_id, vendor_id, template_id, quantity, notes, now, now, source_key, acknowledged_at))
                item_id = int(cursor.lastrowid)
            else:
                item_id = int(existing["id"])
                db.execute("UPDATE order_list_items SET vendor_id = ?, template_id = ?, quantity_requested = ?, notes = ?, updated_at = ?, order_source_key = ?, restriction_acknowledged_at = ? WHERE id = ?", (vendor_id, template_id, quantity, notes, now, source_key, acknowledged_at, item_id))
            db.commit()
            return jsonify({"ok": True, "itemId": item_id, "partNumber": str(part["part_number"]), "vendor": str(source["vendor"]), "templateName": str(source["template_name"])})

    def stamp_centered(page: fitz.Page, box: list[float] | None, text: str, fontsize: float = 10.0) -> None:
        if not box or not text:
            return
        rect = fitz.Rect(*[float(value) for value in box])
        rect = fitz.Rect(rect.x0 + 1.5, rect.y0 + 1.5, rect.x1 - 1.5, rect.y1 - 1.5)
        page.insert_textbox(rect, str(text), fontsize=fontsize, fontname="helv", align=fitz.TEXT_ALIGN_CENTER)

    def fill_template(template_id: str, requested_sources: list[tuple[dict, int]]) -> bytes:
        template = active_templates[template_id]
        source_pdf = order_forms_dir / str(template["file_name"])
        document = fitz.open(source_pdf)
        try:
            today_text = date.today().strftime("%m/%d/%Y")
            for page_index, page in enumerate(document, start=1):
                sample = next((source for source, _ in requested_sources if int(source["page"]) == page_index), None)
                date_box = sample.get("date_box") if sample else _find_label_box(page, "Date:")
                office_box = sample.get("office_box") if sample else (_find_label_box(page, "Office #") or _find_label_box(page, "Office"))
                stamp_centered(page, date_box, today_text, 9.5)
                stamp_centered(page, office_box, DEFAULT_OFFICE_NUMBER, 10.0)
            totals: dict[tuple[int, tuple[float, ...]], int] = {}
            for source, quantity in requested_sources:
                box = tuple(float(value) for value in source["request_box"])
                totals[(int(source["page"]), box)] = totals.get((int(source["page"]), box), 0) + int(quantity)
            for (page_number, box), quantity in totals.items():
                stamp_centered(document[page_number - 1], list(box), str(quantity), 10.5)
            output = BytesIO()
            document.save(output, garbage=4, deflate=True)
            return output.getvalue()
        finally:
            document.close()

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
            rows = db.execute("SELECT order_list_items.*, parts.part_number, parts.description FROM order_list_items JOIN parts ON parts.id = order_list_items.part_id WHERE order_list_items.warehouse_id = ? ORDER BY order_list_items.id", (warehouse_id,)).fetchall()
        if not rows:
            return jsonify({"error": "The order list is empty."}), 400
        grouped: dict[str, list[tuple[dict, int]]] = {}
        unmapped: list[str] = []
        for row in rows:
            source = resolve_source(str(row["order_source_key"] or ""), str(row["part_number"]))
            if source is None:
                unmapped.append(str(row["part_number"]))
                continue
            restrictions = list(source.get("restrictions", []))
            if restrictions and not str(row["restriction_acknowledged_at"] or "").strip():
                return jsonify({"error": f"{row['part_number']} has ordering restrictions that still need acknowledgement.", "restrictions": restrictions}), 409
            grouped.setdefault(str(source["template_id"]), []).append((source, int(row["quantity_requested"])))
        if unmapped:
            return jsonify({"error": "Some staged items were added before corporate form mapping was selected. Re-add these items before generating forms.", "unmappedParts": unmapped}), 409
        zip_buffer = BytesIO()
        generated_names: list[str] = []
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for template_id, requested_sources in sorted(grouped.items()):
                filled_pdf = fill_template(template_id, requested_sources)
                base = Path(str(active_templates[template_id]["file_name"])).stem
                filename = f"Office_{DEFAULT_OFFICE_NUMBER}_{_safe_filename(base)}_{date.today().isoformat()}.pdf"
                archive.writestr(filename, filled_pdf)
                generated_names.append(filename)
            archive.writestr("README.txt", f"Generated by ShopFlow for Office {DEFAULT_OFFICE_NUMBER} - {DEFAULT_LOCATION}\nDate: {date.today().strftime('%m/%d/%Y')}\n\nFiles:\n- " + "\n- ".join(generated_names))
        zip_buffer.seek(0)
        response = send_file(zip_buffer, mimetype="application/zip", as_attachment=True, download_name=f"Office_{DEFAULT_OFFICE_NUMBER}_Order_Forms_{date.today().isoformat()}.zip")
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
        index = html.lower().rfind("</body>")
        html = html[:index] + f'<script src="{marker}"></script>' + html[index:]
        response.set_data(html)
        response.headers["Content-Length"] = str(len(response.get_data()))
        return response

    app.extensions["shopflow_order_form_plugin"] = {
        "office_number": DEFAULT_OFFICE_NUMBER,
        "location": DEFAULT_LOCATION,
        "template_count": len(active_templates),
        "source_cache": source_cache,
    }
