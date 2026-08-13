from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Callable

import fitz
from flask import jsonify

from order_form_plugin import FORM_META, _clean, _column_config, _infer_vendor, _part_candidates

OFFICE_CODE = "93"
WAREHOUSE_NAME = "Davenport"
CATALOG_EXCLUDED_FORMS = {
    "Lumber Order Sheet Test.pdf",  # reference/verification sheet, not a live ordering form
    "BF Walls & Accessories (1).pdf",  # no dependable internal item number column in this form
}
CORPORATE_VENDOR_NAMES = {"Corporate Purchasing", "Bath Fitter Corporate", "Lumber Vendor Choice"}

CATEGORY_PREFIXES = (
    (("AID", "SAF", "PPE", "SFT", "SAFT"), "Safety / PPE"),
    (("TOL", "TOO"), "Tools"),
    (("SND", "ADH", "ADV", "AH"), "Supplies / Adhesives"),
    (("FTG", "PVC"), "Fittings / Plumbing"),
    (("FXT", "SP"), "Fixtures / Shower Accessories"),
    (("REM",), "Lumber / Building Materials"),
    (("FAC", "BIN", "WHSE"), "Facilities / Warehouse"),
    (("PLU", "PRO", "MFG"), "Install / Sales Supplies"),
)


def _connect(db_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def _normalize_key(value: object) -> str:
    return _clean(value).upper()


def _looks_like_internal_item(value: object) -> bool:
    text = _clean(value)
    if not text or len(text) > 32 or len(text) < 3:
        return False
    if text.lower() in {
        "requested", "internal item#", "internal item #", "item#", "item #", "order qty", "amount",
        "tools", "screws", "misc.", "misc", "drywall", "plywood", "foam and insulation",
        "framing studs", "fraiming studs", "moulding",
    }:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._\-/]*", text))


def _category_for(part_number: str, template_id: str) -> str:
    normalized = _normalize_key(part_number).replace(" ", "")
    for prefixes, category in CATEGORY_PREFIXES:
        if normalized.startswith(prefixes):
            return category
    template_categories = {
        "first-aid": "Safety / PPE",
        "ppe": "Safety / PPE",
        "fleet": "Fleet Supplies",
        "facilities": "Facilities / Warehouse",
        "84-lumber": "Lumber / Building Materials",
        "home-depot": "Lumber / Building Materials",
        "lowes": "Lumber / Building Materials",
        "ferguson": "Fixtures / Plumbing",
        "rf-fager": "Fittings / Plumbing",
        "seachrome": "Shower Accessories",
        "zoe": "Shower Accessories",
        "alumax": "Shower Door Parts",
        "basco": "Shower Door Parts",
        "sales-kit": "Install / Sales Supplies",
    }
    return template_categories.get(template_id, "General Supplies")


def _ensure_template(db: sqlite3.Connection, filename: str, meta: tuple) -> None:
    template_id, template_name, _default_vendor, active = meta
    if not active:
        return
    now = datetime.now().isoformat()
    existing = db.execute("SELECT template_id FROM order_form_templates WHERE template_id = ?", (template_id,)).fetchone()
    notes = f"Corporate PDF template: {filename}"
    if existing is None:
        db.execute(
            "INSERT INTO order_form_templates (template_id, name, form_variant, notes, created_at, updated_at) VALUES (?, ?, 'corporate_pdf', ?, ?, ?)",
            (template_id, template_name, notes, now, now),
        )
    else:
        db.execute(
            "UPDATE order_form_templates SET name = ?, form_variant = 'corporate_pdf', notes = ?, updated_at = ? WHERE template_id = ?",
            (template_name, notes, now, template_id),
        )


def _ensure_vendor(db: sqlite3.Connection, vendor_name: str, template_id: str) -> int:
    name = _clean(vendor_name) or "Corporate Purchasing"
    existing = db.execute(
        "SELECT id, linked_template_id FROM vendors WHERE LOWER(name) = LOWER(?) ORDER BY id LIMIT 1", (name,)
    ).fetchone()
    if existing is not None:
        if not _clean(existing["linked_template_id"]):
            db.execute("UPDATE vendors SET linked_template_id = ? WHERE id = ?", (template_id, int(existing["id"])))
        return int(existing["id"])
    cursor = db.execute(
        "INSERT INTO vendors (name, contact, email, phone, lead_time_days, linked_template_id) VALUES (?, '', '', '', 0, ?)",
        (name, template_id),
    )
    return int(cursor.lastrowid)


def _ensure_warehouse(db: sqlite3.Connection) -> int:
    existing = db.execute("SELECT id FROM warehouses WHERE code = ?", (OFFICE_CODE,)).fetchone()
    if existing is not None:
        db.execute("UPDATE warehouses SET is_active = 1 WHERE id = ?", (int(existing["id"]),))
        return int(existing["id"])
    cursor = db.execute(
        "INSERT INTO warehouses (name, code, is_active) VALUES (?, ?, 1)", (WAREHOUSE_NAME, OFFICE_CODE)
    )
    return int(cursor.lastrowid)


def _scan_catalog(order_forms_dir: Path) -> tuple[dict[str, dict], dict]:
    items: dict[str, dict] = {}
    stats = {
        "formsScanned": 0,
        "rowsReviewed": 0,
        "candidateRows": 0,
        "skippedMissingInternalId": 0,
        "skippedInvalidInternalId": 0,
        "missingPdfFiles": [],
    }

    for filename, meta in FORM_META.items():
        template_id, template_name, default_vendor, active = meta
        if not active or filename in CATALOG_EXCLUDED_FORMS:
            continue
        pdf_path = order_forms_dir / filename
        if not pdf_path.exists():
            stats["missingPdfFiles"].append(filename)
            continue
        document = fitz.open(pdf_path)
        stats["formsScanned"] += 1
        try:
            for page_index, page in enumerate(document):
                tables = page.find_tables().tables
                if not tables:
                    continue
                table = max(tables, key=lambda item: item.row_count * item.col_count)
                rows = table.extract()
                config = _column_config(filename, page_index + 1)
                part_index = config.get("part")
                description_index = config.get("description")
                vendor_item_index = config.get("vendor_item")
                vendor_index = config.get("vendor")
                header_rows = int(config.get("header_rows") or 0)

                for row_index, row in enumerate(rows):
                    if row_index < header_rows:
                        continue
                    stats["rowsReviewed"] += 1
                    values = list(row) + [None] * max(table.col_count - len(row), 0)
                    part_raw = values[int(part_index)] if part_index is not None and int(part_index) < len(values) else ""
                    if not _clean(part_raw):
                        stats["skippedMissingInternalId"] += 1
                        continue
                    candidates = _part_candidates(part_raw, "")
                    if not candidates:
                        stats["skippedMissingInternalId"] += 1
                        continue

                    description = _clean(values[int(description_index)]) if description_index is not None and int(description_index) < len(values) else ""
                    vendor_item = _clean(values[int(vendor_item_index)]) if vendor_item_index is not None and int(vendor_item_index) < len(values) else ""
                    vendor_raw = _clean(values[int(vendor_index)]) if vendor_index is not None and int(vendor_index) < len(values) else vendor_item
                    vendor = _infer_vendor(vendor_raw, default_vendor)

                    for candidate in candidates:
                        if not _looks_like_internal_item(candidate):
                            stats["skippedInvalidInternalId"] += 1
                            continue
                        stats["candidateRows"] += 1
                        key = _normalize_key(candidate)
                        entry = items.setdefault(
                            key,
                            {
                                "partNumber": _clean(candidate),
                                "description": description,
                                "category": _category_for(candidate, template_id),
                                "sources": [],
                            },
                        )
                        if description and len(description) > len(entry["description"] or ""):
                            entry["description"] = description
                        source = {
                            "vendor": vendor,
                            "templateId": template_id,
                            "templateName": template_name,
                            "fileName": filename,
                        }
                        if source not in entry["sources"]:
                            entry["sources"].append(source)
        finally:
            document.close()

    return items, stats


def _choose_primary_source(sources: list[dict]) -> dict:
    non_corporate = [source for source in sources if source["vendor"] not in CORPORATE_VENDOR_NAMES]
    candidates = non_corporate or sources
    return sorted(candidates, key=lambda source: (source["vendor"].lower(), source["templateId"]))[0]


def sync_office93_catalog(db_path: str | Path, base_dir: str | Path) -> dict:
    database_path = Path(db_path)
    order_forms_dir = Path(base_dir) / "order_forms"
    items, scan_stats = _scan_catalog(order_forms_dir)
    now = datetime.now().isoformat()

    with _connect(database_path) as db:
        warehouse_id = _ensure_warehouse(db)
        for filename, meta in FORM_META.items():
            _ensure_template(db, filename, meta)

        inserted = 0
        updated = 0
        vendor_ids: dict[tuple[str, str], int] = {}

        for item in sorted(items.values(), key=lambda value: _normalize_key(value["partNumber"])):
            if not item["sources"]:
                continue
            primary = _choose_primary_source(item["sources"])
            vendor_key = (primary["vendor"].lower(), primary["templateId"])
            vendor_id = vendor_ids.get(vendor_key)
            if vendor_id is None:
                vendor_id = _ensure_vendor(db, primary["vendor"], primary["templateId"])
                vendor_ids[vendor_key] = vendor_id

            existing = db.execute(
                "SELECT * FROM parts WHERE warehouse_id = ? AND UPPER(TRIM(part_number)) = ?",
                (warehouse_id, _normalize_key(item["partNumber"])),
            ).fetchone()
            description = item["description"] or f"Catalog item {item['partNumber']}"
            scan_code = _normalize_key(item["partNumber"])
            if existing is None:
                db.execute(
                    """
                    INSERT INTO parts (
                        warehouse_id, part_number, scan_code, description, category, item_type,
                        stock, reorder_point, vendor_id, unit_cost, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'stocked', 0, 0, ?, 0, ?, ?)
                    """,
                    (warehouse_id, item["partNumber"], scan_code, description, item["category"], vendor_id, now, now),
                )
                inserted += 1
            else:
                db.execute(
                    """
                    UPDATE parts
                    SET description = ?, category = ?, scan_code = CASE WHEN TRIM(scan_code) = '' THEN ? ELSE scan_code END,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (description, item["category"], scan_code, now, int(existing["id"])),
                )
                updated += 1

        db.commit()
        part_count = int(db.execute("SELECT COUNT(*) AS count FROM parts WHERE warehouse_id = ?", (warehouse_id,)).fetchone()["count"])
        vendor_count = int(db.execute("SELECT COUNT(*) AS count FROM vendors").fetchone()["count"])

    return {
        "officeNumber": OFFICE_CODE,
        "location": WAREHOUSE_NAME,
        "warehouseId": warehouse_id,
        "catalogPartCount": part_count,
        "canonicalItemsFound": len(items),
        "inserted": inserted,
        "updated": updated,
        "vendorCount": vendor_count,
        **scan_stats,
    }


def _catalog_status(db_path: Path) -> dict:
    with _connect(db_path) as db:
        warehouse = db.execute("SELECT id, name, code FROM warehouses WHERE code = ?", (OFFICE_CODE,)).fetchone()
        if warehouse is None:
            return {"officeNumber": OFFICE_CODE, "location": WAREHOUSE_NAME, "warehouseId": None, "catalogPartCount": 0}
        count = int(db.execute("SELECT COUNT(*) AS count FROM parts WHERE warehouse_id = ?", (int(warehouse["id"]),)).fetchone()["count"])
        return {
            "officeNumber": OFFICE_CODE,
            "location": str(warehouse["name"]),
            "warehouseId": int(warehouse["id"]),
            "catalogPartCount": count,
        }


def register_office93_catalog(
    app,
    *,
    db_path: str | Path,
    base_dir: str | Path,
    permission_checker: Callable[[str], bool] | None = None,
) -> None:
    if app.extensions.get("shopflow_office93_catalog"):
        return

    database_path = Path(db_path)
    root = Path(base_dir)
    status = _catalog_status(database_path)
    if int(status.get("catalogPartCount") or 0) == 0:
        status = sync_office93_catalog(database_path, root)

    def can_edit() -> bool:
        if permission_checker is None:
            return True
        try:
            return bool(permission_checker("edit_records"))
        except Exception:
            return False

    @app.get("/api/office93/catalog-status")
    def office93_catalog_status():
        return jsonify(_catalog_status(database_path))

    @app.post("/api/office93/catalog-sync")
    def office93_catalog_sync():
        if not can_edit():
            return jsonify({"error": "Edit access required to sync the Office 93 catalog."}), 403
        return jsonify(sync_office93_catalog(database_path, root))

    app.extensions["shopflow_office93_catalog"] = status
