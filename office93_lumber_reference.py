from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


OFFICE_CODE = "93"

# Canonical inventory rows from the consolidated Lumber Order Sheet Test.
# The consolidated sheet is reference-only for catalog seeding. Actual ordering
# still routes to the separate Lowe's, Home Depot, and 84 Lumber PDF forms.
LUMBER_REFERENCE_ITEMS = [
    ("REM931", "1/2\" x 4' x 8' Moisture Resistant Drywall (34/Bundle)", "Lowe's", "lowes"),
    ("REM984", "5/8\" x 4' x 8' Fire Shield Drywall", "Lowe's", "lowes"),
    ("REM931A", "1/2\" x 4' x 8' Plywood (72/Bundle)", "Lowe's", "lowes"),
    ("REM932", "3/16 (5mm) Luan Plywood Underlayment", "Lowe's", "lowes"),
    ("REM934", "5/8\" x 4' x 8' CDX Plywood (19/32\") (58/Bundle)", "Lowe's", "lowes"),
    ("REM935", "3/4\" x 4' x 8' CDX Plywood (23/32\") (48/Bundle)", "Lowe's", "lowes"),
    ("REM936", "Styrofoam Panel 3/4\" x 4' x 8' Green Kingspan", "Lowe's", "lowes"),
    ("REM936A", "Kingspan 1/2\" x 4' x 8' Styrofoam Panel", "Lowe's", "lowes"),
    ("REM936-HD", "Owens Corning Foamular Rigid Foam Board 1/2\" x 4' x 8' Pink", "Home Depot", "home-depot"),
    ("REM937", "Kingspan GreenGuard Fanfold Sheet 1/4\" x 4' (25/Bundle)", "Lowe's", "lowes"),
    ("REM937B", "Foamular 1/4\" x 4' x 50' R-1 Fanfold Rigid Foam Board", "Home Depot", "home-depot"),
    ("REM953", "Roll Insulation R-13", "Lowe's", "lowes"),
    ("REM938", "2\" x 4\" x 8' Framing Stud (294/Skid)", "Lowe's", "lowes"),
    ("REM938B", "2\" x 3\" x 8' Stud", "Lowe's", "lowes"),
    ("REM938D", "2\" x 12\" x 16' Stud", "84 Lumber", "84-lumber"),
    ("REM940", "1\" x 4\" x 8' #2 Grade Pine Lumber", "Lowe's", "lowes"),
    ("REM951", "2\" x 6\" x 12' Framing Lumber", "Lowe's", "lowes"),
    ("REM939", "1\" x 3\" x 8' Furring Strip (6/Bundle)", "Lowe's", "lowes"),
    ("REM957", "2\" x 6\" x 8' Lumber", "Lowe's", "lowes"),
    ("SND507C", "Drywall Screws 1\" x #8 Coarse Thread - 5 lb Box", "Lowe's", "lowes"),
    ("SND507D", "Drywall Screws 1\" x #6 Bugle Head Fine Thread - 25 lb Box", "Home Depot", "home-depot"),
    ("SND508", "Drywall Screws 1 1/4\" x #6 - 25 lb Tub", "Lowe's", "lowes"),
    ("SND509", "Drywall Screws 1 5/8\" x #6 - 25 lb Tub", "Lowe's", "lowes"),
    ("SND510", "Drywall Screws 2\" x #8 - 25 lb Tub", "84 Lumber", "84-lumber"),
    ("SND510B", "Drywall Screws 2\" x #6 - 25 lb Tub", "Home Depot", "home-depot"),
    ("SND511", "Drywall Screws 2 1/2\" x #8 - 25 lb Tub", "Lowe's", "lowes"),
    ("SND512", "Drywall Screws 3\" x #8 - 25 lb Tub", "Lowe's", "lowes"),
    ("REM2000", "Quarter Round Moulding 3/4\" x 3/4\" x 12' Primed White PVC", "Lowe's", "lowes"),
    ("REM62018", "Baseboard Moulding 3-1/4\" x 96\" Colonial Wood Finger Jointed Primed White", "Lowe's", "lowes"),
    ("REM2021", "Baseboard Moulding 4-1/4\" x 96\" Colonial MDF Primed White", "Lowe's", "lowes"),
    ("SAF005", "5 Gallon Bucket", "84 Lumber", "84-lumber"),
    ("TOL654", "Drywall 4 ft Square", "Lowe's", "lowes"),
    ("TOL721B", "Wagner Furno 500 Heat Gun Corded 1500 Watt Variable Control", "Home Depot", "home-depot"),
    ("WHSE039", "OSHA Approved 11-Watt LED White Emergency Light w/6 Volt Battery", "Home Depot", "home-depot"),
    ("WHSE040", "OSHA Approved 14-Watt LED White Exit Sign w/4.8 Volt Battery", "Home Depot", "home-depot"),
]


def _category(part_number: str) -> str:
    value = part_number.upper()
    if value.startswith("REM"):
        return "Lumber / Building Materials"
    if value.startswith("SND"):
        return "Supplies / Adhesives"
    if value.startswith("SAF"):
        return "Safety / PPE"
    if value.startswith("TOL"):
        return "Tools"
    if value.startswith("WHSE"):
        return "Facilities / Warehouse"
    return "General Supplies"


def _ensure_vendor(db: sqlite3.Connection, name: str, template_id: str) -> int:
    row = db.execute(
        "SELECT id, linked_template_id FROM vendors WHERE LOWER(name) = LOWER(?) ORDER BY id LIMIT 1",
        (name,),
    ).fetchone()
    if row is not None:
        if not str(row["linked_template_id"] or "").strip():
            db.execute("UPDATE vendors SET linked_template_id = ? WHERE id = ?", (template_id, int(row["id"])))
        return int(row["id"])
    cursor = db.execute(
        "INSERT INTO vendors (name, contact, email, phone, lead_time_days, linked_template_id) VALUES (?, '', '', '', 0, ?)",
        (name, template_id),
    )
    return int(cursor.lastrowid)


def sync_lumber_reference_items(db_path: str | Path) -> dict:
    database_path = Path(db_path)
    db = sqlite3.connect(database_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        warehouse = db.execute("SELECT id FROM warehouses WHERE code = ?", (OFFICE_CODE,)).fetchone()
        if warehouse is None:
            return {"inserted": 0, "updated": 0, "reason": "Office 93 warehouse is not initialized."}
        warehouse_id = int(warehouse["id"])
        now = datetime.now().isoformat()
        inserted = 0
        updated = 0
        vendor_cache: dict[tuple[str, str], int] = {}

        for part_number, description, vendor_name, template_id in LUMBER_REFERENCE_ITEMS:
            key = (vendor_name.lower(), template_id)
            vendor_id = vendor_cache.get(key)
            if vendor_id is None:
                vendor_id = _ensure_vendor(db, vendor_name, template_id)
                vendor_cache[key] = vendor_id

            existing = db.execute(
                "SELECT id FROM parts WHERE warehouse_id = ? AND UPPER(TRIM(part_number)) = UPPER(?)",
                (warehouse_id, part_number),
            ).fetchone()
            if existing is None:
                db.execute(
                    """
                    INSERT INTO parts (
                        warehouse_id, part_number, scan_code, description, category, item_type,
                        stock, reorder_point, vendor_id, unit_cost, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'stocked', 0, 0, ?, 0, ?, ?)
                    """,
                    (warehouse_id, part_number, part_number.upper(), description, _category(part_number), vendor_id, now, now),
                )
                inserted += 1
            else:
                db.execute(
                    "UPDATE parts SET description = ?, category = ?, updated_at = ? WHERE id = ?",
                    (description, _category(part_number), now, int(existing["id"])),
                )
                updated += 1
        db.commit()
        return {"inserted": inserted, "updated": updated, "referenceItems": len(LUMBER_REFERENCE_ITEMS)}
    finally:
        db.close()
