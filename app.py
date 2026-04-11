from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, send_file


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "shopflow.db"

app = Flask(__name__, template_folder="templates", static_folder="assets", static_url_path="/assets")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error: object) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    with closing(db):
        needs_rebuild = schema_needs_rebuild(db)
        if needs_rebuild:
            rebuild_schema(db)
            seed_database(db)
        else:
            ensure_schema(db)
            ensure_optional_columns(db)
            normalize_purchase_order_statuses(db)
            if not has_seed_data(db):
                seed_database(db)


def schema_needs_rebuild(db: sqlite3.Connection) -> bool:
    tables = {row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "warehouses" not in tables:
        return True
    if "parts" not in tables:
        return True
    if "stock_transfers" not in tables:
        return False
    columns = {row["name"] for row in db.execute("PRAGMA table_info(parts)")}
    return "warehouse_id" not in columns


def rebuild_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        PRAGMA foreign_keys = OFF;
        DROP TABLE IF EXISTS job_part_requirements;
        DROP TABLE IF EXISTS jobs;
        DROP TABLE IF EXISTS usage_logs;
        DROP TABLE IF EXISTS receiving_logs;
        DROP TABLE IF EXISTS purchase_orders;
        DROP TABLE IF EXISTS parts;
        DROP TABLE IF EXISTS vendors;
        DROP TABLE IF EXISTS warehouses;
        PRAGMA foreign_keys = ON;
        """
    )
    ensure_schema(db)


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS warehouses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            code TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            lead_time_days INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER NOT NULL,
            part_number TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            stock INTEGER NOT NULL,
            reorder_point INTEGER NOT NULL,
            vendor_id INTEGER NOT NULL,
            unit_cost REAL NOT NULL,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (vendor_id) REFERENCES vendors(id),
            UNIQUE (warehouse_id, part_number)
        );

        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER NOT NULL,
            po_number TEXT NOT NULL UNIQUE,
            vendor_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            received_quantity INTEGER NOT NULL DEFAULT 0,
            eta TEXT NOT NULL,
            notes TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (vendor_id) REFERENCES vendors(id),
            FOREIGN KEY (part_id) REFERENCES parts(id)
        );

        CREATE TABLE IF NOT EXISTS receiving_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            received_by TEXT NOT NULL,
            notes TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (po_id) REFERENCES purchase_orders(id),
            FOREIGN KEY (part_id) REFERENCES parts(id)
        );

        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER NOT NULL,
            job_number TEXT NOT NULL,
            technician TEXT NOT NULL,
            part_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            notes TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (part_id) REFERENCES parts(id)
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER NOT NULL,
            job_number TEXT NOT NULL,
            title TEXT NOT NULL,
            technician TEXT NOT NULL,
            status TEXT NOT NULL,
            notes TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
        );

        CREATE TABLE IF NOT EXISTS job_part_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            required_quantity INTEGER NOT NULL,
            pulled_quantity INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (part_id) REFERENCES parts(id)
        );

        CREATE TABLE IF NOT EXISTS stock_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            from_warehouse_id INTEGER NOT NULL,
            to_warehouse_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            notes TEXT NOT NULL,
            transferred_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (from_warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (to_warehouse_id) REFERENCES warehouses(id)
        );

        CREATE TABLE IF NOT EXISTS reorder_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            vendor_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (part_id) REFERENCES parts(id),
            FOREIGN KEY (vendor_id) REFERENCES vendors(id)
        );
        """
    )
    db.commit()


def ensure_optional_columns(db: sqlite3.Connection) -> None:
    warehouse_columns = {row["name"] for row in db.execute("PRAGMA table_info(warehouses)")}
    if "is_active" not in warehouse_columns:
        db.execute("ALTER TABLE warehouses ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
        db.commit()


def normalize_purchase_order_statuses(db: sqlite3.Connection) -> None:
    status_map = {
        "Awaiting Approval": "Email Pending",
        "Ordered": "Waiting for Part",
        "Shipped": "Waiting for Part",
        "Partially Received": "Waiting for Part",
    }
    for old_status, new_status in status_map.items():
        db.execute(
            "UPDATE purchase_orders SET status = ? WHERE status = ?",
            (new_status, old_status),
        )
    db.commit()


def has_seed_data(db: sqlite3.Connection) -> bool:
    row = db.execute("SELECT COUNT(*) AS count FROM warehouses").fetchone()
    return bool(row["count"])


def next_po_number(db: sqlite3.Connection) -> str:
    row = db.execute(
        """
        SELECT MAX(CAST(SUBSTR(po_number, 4) AS INTEGER)) AS max_po_number
        FROM purchase_orders
        WHERE po_number LIKE 'PO-%'
        """
    ).fetchone()
    max_po_number = row["max_po_number"] or 1000
    return f"PO-{max_po_number + 1}"


def demo_catalog() -> list[dict]:
    catalog_groups = [
        (
            "Drain Assemblies",
            "AquaFlow Plumbing Supply",
            "DRA",
            [
                "Tub drain waste and overflow kit",
                "Toe-touch bathtub drain assembly",
                "PVC shower drain base",
                "Brass lift-and-turn tub drain",
                "Linear shower drain grate kit",
                "Bathtub trip lever conversion kit",
            ],
            24.0,
        ),
        (
            "Valves",
            "BathBuild Distributors",
            "VAL",
            [
                "Pressure-balance shower valve",
                "Single-handle mixing valve",
                "Thermostatic valve cartridge",
                "Roman tub rough-in valve",
                "Transfer diverter valve body",
                "Hot-side ceramic stem cartridge",
            ],
            39.0,
        ),
        (
            "Sealants",
            "BathBuild Distributors",
            "SEA",
            [
                "Bathroom silicone sealant tube",
                "Color-matched tub seam sealant",
                "Acrylic latex bath caulk",
                "Waterproof construction adhesive",
                "Mildew-resistant corner bead adhesive",
                "Plumber's putty tub seal pack",
            ],
            5.0,
        ),
        (
            "Supply Lines",
            "AquaFlow Plumbing Supply",
            "SUP",
            [
                "Braided faucet supply line 12in",
                "Braided faucet supply line 20in",
                "Braided toilet supply line 16in",
                "Braided shutoff supply line 30in",
                "Flexible shower hose connection line",
                "Compression stop valve kit",
            ],
            8.5,
        ),
        (
            "Trim Kits",
            "BathBuild Distributors",
            "TRM",
            [
                "Chrome shower trim plate kit",
                "Brushed nickel trim plate kit",
                "Matte black handle and escutcheon set",
                "Tub spout with diverter trim",
                "Hand shower slide bar trim kit",
                "Overflow faceplate and screws kit",
            ],
            26.0,
        ),
        (
            "Faucets",
            "BathBuild Distributors",
            "FAC",
            [
                "Single-hole vanity faucet",
                "Widespread lav faucet set",
                "Centerset sink faucet",
                "Roman tub filler trim",
                "Wall-mount lavatory faucet",
                "Utility sink service faucet",
            ],
            48.0,
        ),
        (
            "Install Kits",
            "BathBuild Distributors",
            "KIT",
            [
                "Tub surround install screw pack",
                "Shower wall panel leveling shim kit",
                "Anchor and washer install pack",
                "Trim clip and retainer pack",
                "Access panel mounting clip set",
                "Tub apron fastening kit",
            ],
            6.5,
        ),
        (
            "Shower Hardware",
            "AquaFlow Plumbing Supply",
            "SHW",
            [
                "Rain shower head 2.0 gpm",
                "Hand shower wand kit",
                "Dual-function diverter trim",
                "Shower arm and flange set",
                "Ceiling drop ell supply elbow",
                "Slide bar mounting bracket kit",
            ],
            18.0,
        ),
        (
            "Toilet Parts",
            "AquaFlow Plumbing Supply",
            "TOL",
            [
                "Wax-free toilet seal kit",
                "Closet bolt and cap set",
                "Fill valve replacement kit",
                "Flush valve flapper kit",
                "Toilet tank lever handle",
                "Closet flange repair ring",
            ],
            7.5,
        ),
        (
            "P-Traps",
            "AquaFlow Plumbing Supply",
            "PTR",
            [
                "PVC lavatory P-trap kit",
                "Chrome lavatory P-trap kit",
                "ABS tubular trap adapter set",
                "Slip-joint trap washer assortment",
                "Deep seal trap bend kit",
                "Trap arm extension kit",
            ],
            9.0,
        ),
    ]

    catalog: list[dict] = []
    running_index = 0
    for group_index, (category, vendor_name, prefix, descriptions, base_cost) in enumerate(catalog_groups, start=1):
        for item_index, description in enumerate(descriptions, start=1):
            running_index += 1
            reorder_point = 4 + ((running_index + group_index + item_index) % 7) * 2
            unit_cost = round(base_cost + ((item_index - 1) * 2.35) + (group_index * 0.85), 2)
            catalog.append(
                {
                    "part_number": f"{prefix}-{group_index:02d}{item_index:02d}",
                    "description": description,
                    "category": category,
                    "vendor_name": vendor_name,
                    "reorder_point": reorder_point,
                    "unit_cost": unit_cost,
                }
            )
    return catalog


def seed_database(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        DELETE FROM reorder_requests;
        DELETE FROM job_part_requirements;
        DELETE FROM jobs;
        DELETE FROM usage_logs;
        DELETE FROM receiving_logs;
        DELETE FROM stock_transfers;
        DELETE FROM purchase_orders;
        DELETE FROM parts;
        DELETE FROM vendors;
        DELETE FROM warehouses;
        DELETE FROM sqlite_sequence;
        """
    )

    warehouses = [
        ("Dallas Bath Supply Hub", "DAL"),
        ("Chicago Plumbing Cage", "CHI"),
        ("Phoenix Install Warehouse", "PHX"),
    ]
    db.executemany("INSERT INTO warehouses (name, code, is_active) VALUES (?, ?, 1)", warehouses)

    vendors = [
        ("AquaFlow Plumbing Supply", "Jordan Ellis", "orders@aquaflow.example", "555-0105", 5),
        ("BathBuild Distributors", "Avery Brooks", "sales@bathbuild.example", "555-0138", 3),
    ]
    db.executemany(
        "INSERT INTO vendors (name, contact, email, phone, lead_time_days) VALUES (?, ?, ?, ?, ?)",
        vendors,
    )

    warehouse_map = {
        row["code"]: row["id"]
        for row in db.execute("SELECT id, code FROM warehouses ORDER BY id").fetchall()
    }
    vendor_map = {
        row["name"]: row["id"]
        for row in db.execute("SELECT id, name FROM vendors ORDER BY id").fetchall()
    }

    catalog = demo_catalog()
    warehouse_codes = ["DAL", "CHI", "PHX"]
    warehouse_offsets = {"DAL": 2, "CHI": 5, "PHX": 8}
    parts = []
    for warehouse_index, warehouse_code in enumerate(warehouse_codes):
        warehouse_id = warehouse_map[warehouse_code]
        offset = warehouse_offsets[warehouse_code]
        for item_index, item in enumerate(catalog, start=1):
            reorder_point = item["reorder_point"]
            base_stock = reorder_point + 7 + ((item_index * 3 + offset) % 22)
            if (item_index + offset) % 8 == 0:
                stock = max(reorder_point - ((item_index % 3) + 1), 0)
            elif (item_index + warehouse_index) % 11 == 0:
                stock = reorder_point
            else:
                stock = base_stock
            parts.append(
                (
                    warehouse_id,
                    item["part_number"],
                    item["description"],
                    item["category"],
                    stock,
                    reorder_point,
                    vendor_map[item["vendor_name"]],
                    item["unit_cost"],
                )
            )
    db.executemany(
        """
        INSERT INTO parts
            (warehouse_id, part_number, description, category, stock, reorder_point, vendor_id, unit_cost)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        parts,
    )

    part_map = {
        (row["warehouse_id"], row["part_number"]): row["id"]
        for row in db.execute("SELECT id, warehouse_id, part_number FROM parts").fetchall()
    }

    now = datetime.now()

    demo_jobs = {
        "DAL": [("DAL-41027", "Dallas Install Crew A"), ("DAL-41031", "Dallas Repair Crew B")],
        "CHI": [("CHI-52018", "Chicago Install Crew A"), ("CHI-52024", "Chicago Service Crew B")],
        "PHX": [("PHX-61012", "Phoenix Install Crew A"), ("PHX-61019", "Phoenix Service Crew B")],
    }

    for warehouse_index, warehouse_code in enumerate(warehouse_codes):
        warehouse_id = warehouse_map[warehouse_code]
        part_keys = [key for key in part_map if key[0] == warehouse_id]
        part_keys.sort(key=lambda key: key[1])

        low_stock_keys = [
            key
            for key in part_keys
            if db.execute(
                "SELECT stock, reorder_point FROM parts WHERE id = ?",
                (part_map[key],),
            ).fetchone()["stock"]
            <= db.execute(
                "SELECT stock, reorder_point FROM parts WHERE id = ?",
                (part_map[key],),
            ).fetchone()["reorder_point"]
        ]
        if len(low_stock_keys) < 3:
            low_stock_keys = part_keys[:3]

        po_specs = [
            (low_stock_keys[0], 10 + warehouse_index, "Email Pending", 6, "Order form generated from low stock alert"),
            (low_stock_keys[1], 14 + warehouse_index, "Waiting for Part", 4, "Email already sent, waiting on inbound shipment"),
            (part_keys[(warehouse_index * 7 + 9) % len(part_keys)], 8 + warehouse_index, "Received", 1, "Recent replenishment received and stocked"),
        ]

        created_offsets = [5, 3, 2]
        received_po_id = None
        received_part_id = None
        received_quantity = None
        for po_index, (part_key, quantity, status, eta_days, notes) in enumerate(po_specs, start=1):
            po_number = f"PO-{1000 + ((warehouse_index * 10) + po_index)}"
            part_id = part_map[part_key]
            vendor_id = db.execute(
                "SELECT vendor_id FROM parts WHERE id = ?",
                (part_id,),
            ).fetchone()["vendor_id"]
            received_quantity_value = quantity if status == "Received" else 0
            db.execute(
                """
                INSERT INTO purchase_orders
                    (warehouse_id, po_number, vendor_id, part_id, quantity, received_quantity, eta, notes, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    warehouse_id,
                    po_number,
                    vendor_id,
                    part_id,
                    quantity,
                    received_quantity_value,
                    (now + timedelta(days=eta_days)).date().isoformat(),
                    notes,
                    status,
                    (now - timedelta(days=created_offsets[po_index - 1])).isoformat(),
                ),
            )
            if status == "Received":
                received_po_id = db.execute(
                    "SELECT id FROM purchase_orders WHERE po_number = ?",
                    (po_number,),
                ).fetchone()["id"]
                received_part_id = part_id
                received_quantity = quantity

        if received_po_id and received_part_id and received_quantity:
            db.execute(
                """
                INSERT INTO receiving_logs (po_id, part_id, quantity, received_by, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    received_po_id,
                    received_part_id,
                    received_quantity,
                    "Demo Receiver",
                    "Counted and shelved into the supply cage",
                    (now - timedelta(days=1)).isoformat(),
                ),
            )

        active_jobs = demo_jobs[warehouse_code]
        for job_index, (job_number, technician) in enumerate(active_jobs):
            title = "Tub-to-shower conversion" if job_index == 0 else "Bathroom repair follow-up"
            job_cursor = db.execute(
                """
                INSERT INTO jobs (warehouse_id, job_number, title, technician, status, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    warehouse_id,
                    job_number,
                    title,
                    technician,
                    "Active",
                    "Seeded demo job",
                    (now - timedelta(hours=(job_index * 4) + 2)).isoformat(),
                ),
            )
            job_id = int(job_cursor.lastrowid)
            for allocation_index in range(3):
                part_key = part_keys[(warehouse_index * 13 + job_index * 5 + allocation_index * 3) % len(part_keys)]
                quantity = 1 + ((warehouse_index + allocation_index + job_index) % 3)
                part_id = part_map[part_key]
                db.execute(
                    """
                    INSERT INTO job_part_requirements (job_id, part_id, required_quantity, pulled_quantity, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        part_id,
                        quantity + 1,
                        quantity,
                        (now - timedelta(hours=(job_index * 4) + allocation_index + 1)).isoformat(),
                    ),
                )
                db.execute(
                    """
                    INSERT INTO usage_logs (warehouse_id, job_number, technician, part_id, quantity, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        warehouse_id,
                        job_number,
                        technician,
                        part_id,
                        quantity,
                        "Active install allocation",
                        (now - timedelta(hours=(job_index * 4) + allocation_index)).isoformat(),
                    ),
                )

        for history_index in range(12):
            part_key = part_keys[(warehouse_index * 17 + history_index * 4 + 11) % len(part_keys)]
            db.execute(
                """
                INSERT INTO usage_logs (warehouse_id, job_number, technician, part_id, quantity, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    warehouse_id,
                    f"{warehouse_code}-HIST-{700 + history_index}",
                    f"{warehouse_code} Maintenance Team",
                    part_map[part_key],
                    1 + ((history_index + warehouse_index) % 4),
                    "Historical demo usage",
                    (now - timedelta(days=history_index + 2, hours=warehouse_index + history_index)).isoformat(),
                ),
            )
    db.commit()


def rows(query: str, params: tuple = ()) -> list[dict]:
    db = get_db()
    return [dict(row) for row in db.execute(query, params).fetchall()]


def selected_warehouse_id() -> int:
    db = get_db()
    requested = request.args.get("warehouseId") or (request.get_json(silent=True) or {}).get("warehouseId")
    if requested:
        return int(requested)
    return db.execute("SELECT id FROM warehouses WHERE is_active = 1 ORDER BY name LIMIT 1").fetchone()["id"]


def currentWarehouseIs(warehouse_id: int) -> bool:
    requested = request.args.get("warehouseId") or (request.get_json(silent=True) or {}).get("warehouseId")
    return bool(requested) and int(requested) == warehouse_id


def bootstrap_payload(warehouse_id: int) -> dict:
    current = rows("SELECT * FROM warehouses WHERE id = ?", (warehouse_id,))
    return {
        "warehouses": rows("SELECT * FROM warehouses ORDER BY name"),
        "activeWarehouses": rows("SELECT * FROM warehouses WHERE is_active = 1 ORDER BY name"),
        "selectedWarehouseId": warehouse_id,
        "selectedWarehouse": current[0] if current else None,
        "vendors": rows("SELECT * FROM vendors ORDER BY name"),
        "parts": rows(
            """
            SELECT parts.*, vendors.name AS vendor_name, warehouses.name AS warehouse_name, warehouses.code AS warehouse_code
            FROM parts
            JOIN vendors ON vendors.id = parts.vendor_id
            JOIN warehouses ON warehouses.id = parts.warehouse_id
            WHERE parts.warehouse_id = ?
            ORDER BY part_number
            """,
            (warehouse_id,),
        ),
        "purchaseOrders": rows(
            """
            SELECT purchase_orders.*, vendors.name AS vendor_name, parts.part_number, parts.description,
                   warehouses.name AS warehouse_name, warehouses.code AS warehouse_code
            FROM purchase_orders
            JOIN vendors ON vendors.id = purchase_orders.vendor_id
            JOIN parts ON parts.id = purchase_orders.part_id
            JOIN warehouses ON warehouses.id = purchase_orders.warehouse_id
            WHERE purchase_orders.warehouse_id = ?
            ORDER BY datetime(purchase_orders.created_at) DESC
            """,
            (warehouse_id,),
        ),
        "receivingLogs": rows(
            """
            SELECT receiving_logs.*, purchase_orders.po_number, parts.part_number, purchase_orders.warehouse_id
            FROM receiving_logs
            LEFT JOIN purchase_orders ON purchase_orders.id = receiving_logs.po_id
            JOIN parts ON parts.id = receiving_logs.part_id
            WHERE purchase_orders.warehouse_id = ?
            ORDER BY datetime(receiving_logs.created_at) DESC
            """,
            (warehouse_id,),
        ),
        "jobs": rows(
            """
            SELECT * FROM jobs
            WHERE warehouse_id = ?
            ORDER BY datetime(created_at) DESC
            """,
            (warehouse_id,),
        ),
        "jobRequirements": rows(
            """
            SELECT job_part_requirements.*, parts.part_number, parts.description
            FROM job_part_requirements
            JOIN jobs ON jobs.id = job_part_requirements.job_id
            JOIN parts ON parts.id = job_part_requirements.part_id
            WHERE jobs.warehouse_id = ?
            ORDER BY jobs.created_at DESC, parts.part_number
            """,
            (warehouse_id,),
        ),
        "usageLogs": rows(
            """
            SELECT usage_logs.*, parts.part_number, parts.description
            FROM usage_logs
            JOIN parts ON parts.id = usage_logs.part_id
            WHERE usage_logs.warehouse_id = ?
            ORDER BY datetime(usage_logs.created_at) DESC
            """,
            (warehouse_id,),
        ),
        "transferLogs": rows(
            """
            SELECT stock_transfers.*, from_warehouse.name AS from_warehouse_name, from_warehouse.code AS from_warehouse_code,
                   to_warehouse.name AS to_warehouse_name, to_warehouse.code AS to_warehouse_code
            FROM stock_transfers
            JOIN warehouses AS from_warehouse ON from_warehouse.id = stock_transfers.from_warehouse_id
            JOIN warehouses AS to_warehouse ON to_warehouse.id = stock_transfers.to_warehouse_id
            WHERE stock_transfers.from_warehouse_id = ? OR stock_transfers.to_warehouse_id = ?
            ORDER BY datetime(stock_transfers.created_at) DESC
            """,
            (warehouse_id, warehouse_id),
        ),
    }


def reorder_form_variant(vendor_name: str) -> str:
    if "AquaFlow" in vendor_name:
        return "aquaflow"
    return "bathbuild"


def reorder_form_context(reorder_id: int) -> dict | None:
    db = get_db()
    row = db.execute(
        """
        SELECT reorder_requests.*, parts.part_number, parts.description, parts.category, parts.unit_cost,
               vendors.name AS vendor_name, vendors.contact AS vendor_contact, vendors.phone AS vendor_phone,
               warehouses.name AS warehouse_name, warehouses.code AS warehouse_code
        FROM reorder_requests
        JOIN parts ON parts.id = reorder_requests.part_id
        JOIN vendors ON vendors.id = reorder_requests.vendor_id
        JOIN warehouses ON warehouses.id = reorder_requests.warehouse_id
        WHERE reorder_requests.id = ?
        """,
        (reorder_id,),
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["form_variant"] = reorder_form_variant(data["vendor_name"])
    data["request_date"] = datetime.fromisoformat(data["created_at"]).strftime("%B %d, %Y")
    data["line_total"] = round(data["quantity"] * data["unit_cost"], 2)
    data["mock_form_name"] = f"{data['vendor_name']} Standard Supply Requisition"
    return data


def purchase_order_form_context(po_id: int) -> dict | None:
    db = get_db()
    row = db.execute(
        """
        SELECT purchase_orders.*, parts.part_number, parts.description, parts.category, parts.unit_cost,
               vendors.name AS vendor_name, vendors.contact AS vendor_contact, vendors.phone AS vendor_phone,
               warehouses.name AS warehouse_name, warehouses.code AS warehouse_code
        FROM purchase_orders
        JOIN parts ON parts.id = purchase_orders.part_id
        JOIN vendors ON vendors.id = purchase_orders.vendor_id
        JOIN warehouses ON warehouses.id = purchase_orders.warehouse_id
        WHERE purchase_orders.id = ?
        """,
        (po_id,),
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["form_variant"] = reorder_form_variant(data["vendor_name"])
    data["request_date"] = datetime.fromisoformat(data["created_at"]).strftime("%B %d, %Y")
    data["line_total"] = round(data["quantity"] * data["unit_cost"], 2)
    data["mock_form_name"] = f"{data['vendor_name']} Standard Supply Requisition"
    return data


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/reorders/<int:reorder_id>/form")
def reorder_form(reorder_id: int):
    context = reorder_form_context(reorder_id)
    if context is None:
        return "Reorder form not found.", 404
    return render_template("order_form.html", reorder=context)


@app.get("/purchase-orders/<int:po_id>/form")
def purchase_order_form(po_id: int):
    context = purchase_order_form_context(po_id)
    if context is None:
        return "Purchase order form not found.", 404
    return render_template("order_form.html", reorder=context)


@app.get("/api/bootstrap")
def api_bootstrap():
    return jsonify(bootstrap_payload(selected_warehouse_id()))


@app.post("/api/vendors")
def save_vendor():
    payload = request.get_json(force=True)
    db = get_db()
    fields = (
        payload["name"].strip(),
        payload["contact"].strip(),
        payload["email"].strip(),
        payload["phone"].strip(),
        int(payload["leadTimeDays"]),
    )
    vendor_id = payload.get("id")
    if vendor_id:
        db.execute(
            """
            UPDATE vendors
            SET name = ?, contact = ?, email = ?, phone = ?, lead_time_days = ?
            WHERE id = ?
            """,
            (*fields, int(vendor_id)),
        )
    else:
        db.execute(
            "INSERT INTO vendors (name, contact, email, phone, lead_time_days) VALUES (?, ?, ?, ?, ?)",
            fields,
        )
    db.commit()
    return jsonify(bootstrap_payload(selected_warehouse_id()))


@app.post("/api/vendors/<int:vendor_id>/delete")
def delete_vendor(vendor_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    part_count = db.execute("SELECT COUNT(*) AS count FROM parts WHERE vendor_id = ?", (vendor_id,)).fetchone()["count"]
    po_count = db.execute("SELECT COUNT(*) AS count FROM purchase_orders WHERE vendor_id = ?", (vendor_id,)).fetchone()["count"]
    if part_count or po_count:
        return jsonify({"error": "This vendor is in use and cannot be deleted."}), 400

    db.execute("DELETE FROM vendors WHERE id = ?", (vendor_id,))
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/warehouses")
def save_warehouse():
    payload = request.get_json(force=True)
    db = get_db()
    fields = (payload["name"].strip(), payload["code"].strip().upper())
    try:
        warehouse_id = payload.get("id")
        if warehouse_id:
            db.execute(
                """
                UPDATE warehouses
                SET name = ?, code = ?
                WHERE id = ?
                """,
                (*fields, int(warehouse_id)),
            )
            selected_id = int(warehouse_id)
        else:
            cursor = db.execute(
                "INSERT INTO warehouses (name, code, is_active) VALUES (?, ?, 1)",
                fields,
            )
            selected_id = int(cursor.lastrowid)
    except sqlite3.IntegrityError:
        return jsonify({"error": "Warehouse name or code already exists."}), 400
    db.commit()
    return jsonify(bootstrap_payload(selected_id))


@app.post("/api/warehouses/<int:warehouse_id>/archive")
def archive_warehouse(warehouse_id: int):
    db = get_db()
    warehouse = db.execute("SELECT * FROM warehouses WHERE id = ?", (warehouse_id,)).fetchone()
    if warehouse is None:
        return jsonify({"error": "Warehouse not found."}), 404

    active_count = db.execute("SELECT COUNT(*) AS count FROM warehouses WHERE is_active = 1").fetchone()["count"]
    if warehouse["is_active"] and active_count <= 1:
        return jsonify({"error": "At least one warehouse must remain active."}), 400

    new_status = 0 if warehouse["is_active"] else 1
    db.execute("UPDATE warehouses SET is_active = ? WHERE id = ?", (new_status, warehouse_id))
    db.commit()

    selected_id = warehouse_id
    if not new_status and currentWarehouseIs(warehouse_id):
        selected_id = db.execute("SELECT id FROM warehouses WHERE is_active = 1 ORDER BY name LIMIT 1").fetchone()["id"]
    return jsonify(bootstrap_payload(selected_id))


@app.post("/api/parts")
def save_part():
    payload = request.get_json(force=True)
    db = get_db()
    fields = (
        int(payload["warehouseId"]),
        payload["partNumber"].strip(),
        payload["description"].strip(),
        payload["category"].strip(),
        int(payload["stock"]),
        int(payload["reorderPoint"]),
        int(payload["vendorId"]),
        float(payload["unitCost"]),
    )
    part_id = payload.get("id")
    try:
        if part_id:
            db.execute(
                """
                UPDATE parts
                SET warehouse_id = ?, part_number = ?, description = ?, category = ?, stock = ?, reorder_point = ?, vendor_id = ?, unit_cost = ?
                WHERE id = ?
                """,
                (*fields, int(part_id)),
            )
        else:
            db.execute(
                """
                INSERT INTO parts
                    (warehouse_id, part_number, description, category, stock, reorder_point, vendor_id, unit_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                fields,
            )
    except sqlite3.IntegrityError:
        return jsonify({"error": "That part number already exists in this warehouse."}), 400
    db.commit()
    return jsonify(bootstrap_payload(int(payload["warehouseId"])))


@app.post("/api/parts/<int:part_id>/delete")
def delete_part(part_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    usage_count = db.execute("SELECT COUNT(*) AS count FROM usage_logs WHERE part_id = ?", (part_id,)).fetchone()["count"]
    po_count = db.execute("SELECT COUNT(*) AS count FROM purchase_orders WHERE part_id = ?", (part_id,)).fetchone()["count"]
    receiving_count = db.execute("SELECT COUNT(*) AS count FROM receiving_logs WHERE part_id = ?", (part_id,)).fetchone()["count"]
    if usage_count or po_count or receiving_count:
        return jsonify({"error": "This part already has history and cannot be deleted."}), 400

    db.execute("DELETE FROM parts WHERE id = ?", (part_id,))
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/purchase-orders")
def create_purchase_order():
    payload = request.get_json(force=True)
    db = get_db()
    po_number = next_po_number(db)
    db.execute(
        """
        INSERT INTO purchase_orders
            (warehouse_id, po_number, vendor_id, part_id, quantity, received_quantity, eta, notes, status, created_at)
        VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'Email Pending', ?)
        """,
        (
            int(payload["warehouseId"]),
            po_number,
            int(payload["vendorId"]),
            int(payload["partId"]),
            int(payload["quantity"]),
            payload["eta"],
            payload.get("notes", "").strip(),
            datetime.now().isoformat(),
        ),
    )
    db.commit()
    return jsonify(bootstrap_payload(int(payload["warehouseId"])))


@app.post("/api/purchase-orders/<int:po_id>/status")
def update_purchase_order_status(po_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    status = payload["status"].strip()
    allowed = {"Email Pending", "Waiting for Part", "Received"}
    if status not in allowed:
        return jsonify({"error": "Invalid purchase order status."}), 400

    db = get_db()
    db.execute("UPDATE purchase_orders SET status = ? WHERE id = ?", (status, po_id))
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/purchase-orders/<int:po_id>/receive")
def receive_purchase_order(po_id: int):
    payload = request.get_json(force=True)
    if not payload.get("verifiedCount"):
        return jsonify({"error": "Count and verify the order before marking it received."}), 400

    db = get_db()
    po = db.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
    if po is None:
        return jsonify({"error": "Purchase order not found."}), 404

    remaining = po["quantity"] - po["received_quantity"]
    if remaining <= 0:
        return jsonify({"error": "This purchase order has already been received."}), 400

    db.execute("UPDATE parts SET stock = stock + ? WHERE id = ?", (remaining, po["part_id"]))
    db.execute(
        """
        INSERT INTO receiving_logs (po_id, part_id, quantity, received_by, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            po["id"],
            po["part_id"],
            remaining,
            payload.get("receivedBy", "").strip() or "Inventory",
            payload.get("notes", "").strip() or "Received from PO workflow",
            datetime.now().isoformat(),
        ),
    )
    db.execute(
        "UPDATE purchase_orders SET received_quantity = quantity, status = 'Received' WHERE id = ?",
        (po_id,),
    )
    db.commit()
    return jsonify(bootstrap_payload(po["warehouse_id"]))


@app.post("/api/reorders")
def create_reorder_request():
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    part = db.execute(
        """
        SELECT parts.*, vendors.id AS resolved_vendor_id
        FROM parts
        JOIN vendors ON vendors.id = parts.vendor_id
        WHERE parts.id = ? AND parts.warehouse_id = ?
        """,
        (int(payload["partId"]), warehouse_id),
    ).fetchone()
    if part is None:
        return jsonify({"error": "Part not found in this warehouse."}), 404

    cursor = db.execute(
        """
        INSERT INTO reorder_requests
            (warehouse_id, part_id, vendor_id, quantity, reason, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'Form Ready', ?)
        """,
        (
            warehouse_id,
            part["id"],
            part["resolved_vendor_id"],
            int(payload["quantity"]),
            payload.get("reason", "").strip(),
            datetime.now().isoformat(),
        ),
    )
    db.commit()
    return jsonify({
        "state": bootstrap_payload(warehouse_id),
        "createdReorderId": int(cursor.lastrowid),
    })


@app.post("/api/purchase-orders/order-more")
def create_order_more_purchase_order():
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    quantity = int(payload["quantity"])
    if quantity <= 0:
        return jsonify({"error": "Quantity must be at least 1."}), 400

    db = get_db()
    part = db.execute(
        """
        SELECT parts.*, vendors.id AS resolved_vendor_id
        FROM parts
        JOIN vendors ON vendors.id = parts.vendor_id
        WHERE parts.id = ? AND parts.warehouse_id = ?
        """,
        (int(payload["partId"]), warehouse_id),
    ).fetchone()
    if part is None:
        return jsonify({"error": "Part not found in this warehouse."}), 404

    cursor = db.execute(
        """
        INSERT INTO purchase_orders
            (warehouse_id, po_number, vendor_id, part_id, quantity, received_quantity, eta, notes, status, created_at)
        VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'Email Pending', ?)
        """,
        (
            warehouse_id,
            next_po_number(db),
            part["resolved_vendor_id"],
            part["id"],
            quantity,
            (datetime.now() + timedelta(days=7)).date().isoformat(),
            payload.get("notes", "").strip() or f"Low stock reorder for {part['part_number']}",
            datetime.now().isoformat(),
        ),
    )
    db.commit()
    return jsonify({
        "state": bootstrap_payload(warehouse_id),
        "createdPoId": int(cursor.lastrowid),
    })


@app.post("/api/reorders/<int:reorder_id>/sent")
def mark_reorder_sent(reorder_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    reorder = db.execute(
        """
        SELECT reorder_requests.*, parts.vendor_id AS part_vendor_id
        FROM reorder_requests
        JOIN parts ON parts.id = reorder_requests.part_id
        WHERE reorder_requests.id = ? AND reorder_requests.warehouse_id = ?
        """,
        (reorder_id, warehouse_id),
    ).fetchone()
    if reorder is None:
        return jsonify({"error": "Reorder request not found."}), 404

    if reorder["status"] == "Sent to PO":
        return jsonify({"error": "That reorder has already been moved to purchase orders."}), 400

    db.execute(
        """
        INSERT INTO purchase_orders
            (warehouse_id, po_number, vendor_id, part_id, quantity, received_quantity, eta, notes, status, created_at)
        VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'Email Pending', ?)
        """,
        (
            warehouse_id,
            next_po_number(db),
            reorder["vendor_id"] or reorder["part_vendor_id"],
            reorder["part_id"],
            reorder["quantity"],
            (datetime.now() + timedelta(days=7)).date().isoformat(),
            reorder["reason"] or "Generated from Order More",
            datetime.now().isoformat(),
        ),
    )
    db.execute(
        "UPDATE reorder_requests SET status = 'Sent to PO' WHERE id = ?",
        (reorder_id,),
    )
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/receiving")
def receive_parts():
    payload = request.get_json(force=True)
    db = get_db()
    po = db.execute("SELECT * FROM purchase_orders WHERE id = ?", (int(payload["poId"]),)).fetchone()
    if po is None:
        return jsonify({"error": "Purchase order not found."}), 404

    quantity = int(payload["quantity"])
    remaining = po["quantity"] - po["received_quantity"]
    if quantity > remaining:
        return jsonify({"error": f"Only {remaining} item(s) remain open on that purchase order."}), 400

    db.execute("UPDATE parts SET stock = stock + ? WHERE id = ?", (quantity, po["part_id"]))
    db.execute(
        """
        INSERT INTO receiving_logs (po_id, part_id, quantity, received_by, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            po["id"],
            po["part_id"],
            quantity,
            payload["receivedBy"].strip(),
            payload.get("notes", "").strip(),
            datetime.now().isoformat(),
        ),
    )
    received_total = po["received_quantity"] + quantity
    status = "Received" if received_total >= po["quantity"] else "Waiting for Part"
    db.execute(
        "UPDATE purchase_orders SET received_quantity = ?, status = ? WHERE id = ?",
        (received_total, status, po["id"]),
    )
    db.commit()
    return jsonify(bootstrap_payload(po["warehouse_id"]))


@app.post("/api/usage")
def allocate_part():
    payload = request.get_json(force=True)
    db = get_db()
    part = db.execute("SELECT * FROM parts WHERE id = ?", (int(payload["partId"]),)).fetchone()
    if part is None:
        return jsonify({"error": "Part not found."}), 404

    quantity = int(payload["quantity"])
    if quantity > part["stock"]:
        return jsonify({"error": "Not enough stock on hand for that allocation."}), 400

    db.execute("UPDATE parts SET stock = stock - ? WHERE id = ?", (quantity, part["id"]))
    db.execute(
        """
        INSERT INTO usage_logs (warehouse_id, job_number, technician, part_id, quantity, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(payload["warehouseId"]),
            payload["jobNumber"].strip(),
            payload["technician"].strip(),
            part["id"],
            quantity,
            payload.get("notes", "").strip(),
            datetime.now().isoformat(),
        ),
    )
    db.commit()
    return jsonify(bootstrap_payload(int(payload["warehouseId"])))


@app.post("/api/jobs")
def create_job():
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    requirements = payload.get("requirements", [])
    valid_requirements = []
    for requirement in requirements:
        part_id = int(requirement["partId"])
        required_quantity = int(requirement["requiredQuantity"])
        if required_quantity <= 0:
            continue
        part = get_db().execute(
            "SELECT id FROM parts WHERE id = ? AND warehouse_id = ?",
            (part_id, warehouse_id),
        ).fetchone()
        if part is None:
            return jsonify({"error": "One of the selected parts is not in this warehouse."}), 400
        valid_requirements.append((part_id, required_quantity))

    if not valid_requirements:
        return jsonify({"error": "Add at least one required part for the job."}), 400

    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO jobs (warehouse_id, job_number, title, technician, status, notes, created_at)
        VALUES (?, ?, ?, ?, 'Active', ?, ?)
        """,
        (
            warehouse_id,
            payload["jobNumber"].strip(),
            payload["title"].strip(),
            payload["technician"].strip(),
            payload.get("notes", "").strip(),
            datetime.now().isoformat(),
        ),
    )
    job_id = int(cursor.lastrowid)
    for part_id, required_quantity in valid_requirements:
        db.execute(
            """
            INSERT INTO job_part_requirements (job_id, part_id, required_quantity, pulled_quantity, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (job_id, part_id, required_quantity, datetime.now().isoformat()),
        )
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/job-parts/<int:requirement_id>/pull")
def pull_job_part(requirement_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    quantity = int(payload["quantity"])
    if quantity <= 0:
        return jsonify({"error": "Pull quantity must be at least 1."}), 400

    db = get_db()
    requirement = db.execute(
        """
        SELECT job_part_requirements.*, jobs.job_number, jobs.technician, jobs.warehouse_id, jobs.status,
               parts.stock, parts.part_number
        FROM job_part_requirements
        JOIN jobs ON jobs.id = job_part_requirements.job_id
        JOIN parts ON parts.id = job_part_requirements.part_id
        WHERE job_part_requirements.id = ?
        """,
        (requirement_id,),
    ).fetchone()
    if requirement is None or requirement["warehouse_id"] != warehouse_id:
        return jsonify({"error": "Job requirement not found."}), 404

    remaining = requirement["required_quantity"] - requirement["pulled_quantity"]
    if quantity > remaining:
        return jsonify({"error": f"Only {remaining} part(s) remain to be pulled for that job."}), 400
    if quantity > requirement["stock"]:
        return jsonify({"error": "Not enough inventory on hand for that pull."}), 400

    db.execute("UPDATE parts SET stock = stock - ? WHERE id = ?", (quantity, requirement["part_id"]))
    db.execute(
        "UPDATE job_part_requirements SET pulled_quantity = pulled_quantity + ? WHERE id = ?",
        (quantity, requirement_id),
    )
    db.execute(
        """
        INSERT INTO usage_logs (warehouse_id, job_number, technician, part_id, quantity, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            warehouse_id,
            requirement["job_number"],
            requirement["technician"],
            requirement["part_id"],
            quantity,
            payload.get("notes", "").strip() or "Pulled for job",
            datetime.now().isoformat(),
        ),
    )
    remaining_requirements = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM job_part_requirements
        WHERE job_id = ? AND pulled_quantity < required_quantity
        """,
        (requirement["job_id"],),
    ).fetchone()["count"]
    db.execute(
        "UPDATE jobs SET status = ? WHERE id = ?",
        ("Ready to Go" if remaining_requirements == 0 else "Active", requirement["job_id"]),
    )
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/reset")
def api_reset():
    db = get_db()
    seed_database(db)
    return jsonify(bootstrap_payload(selected_warehouse_id()))


@app.post("/api/transfers")
def create_transfer():
    payload = request.get_json(force=True)
    db = get_db()
    from_warehouse_id = int(payload["fromWarehouseId"])
    to_warehouse_id = int(payload["toWarehouseId"])
    if from_warehouse_id == to_warehouse_id:
        return jsonify({"error": "Choose two different warehouses for a transfer."}), 400

    part = db.execute(
        "SELECT * FROM parts WHERE id = ? AND warehouse_id = ?",
        (int(payload["partId"]), from_warehouse_id),
    ).fetchone()
    if part is None:
        return jsonify({"error": "Source part not found in the selected warehouse."}), 404

    quantity = int(payload["quantity"])
    if quantity > part["stock"]:
        return jsonify({"error": "Not enough stock in the source warehouse for that transfer."}), 400

    destination_part = db.execute(
        """
        SELECT * FROM parts
        WHERE warehouse_id = ? AND part_number = ?
        """,
        (to_warehouse_id, part["part_number"]),
    ).fetchone()

    if destination_part is None:
        vendor_id = int(payload.get("destinationVendorId") or part["vendor_id"])
        db.execute(
            """
            INSERT INTO parts
                (warehouse_id, part_number, description, category, stock, reorder_point, vendor_id, unit_cost)
            VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                to_warehouse_id,
                part["part_number"],
                part["description"],
                part["category"],
                part["reorder_point"],
                vendor_id,
                part["unit_cost"],
            ),
        )
        destination_part = db.execute(
            """
            SELECT * FROM parts
            WHERE warehouse_id = ? AND part_number = ?
            """,
            (to_warehouse_id, part["part_number"]),
        ).fetchone()

    db.execute("UPDATE parts SET stock = stock - ? WHERE id = ?", (quantity, part["id"]))
    db.execute("UPDATE parts SET stock = stock + ? WHERE id = ?", (quantity, destination_part["id"]))
    db.execute(
        """
        INSERT INTO stock_transfers
            (part_number, description, category, from_warehouse_id, to_warehouse_id, quantity, notes, transferred_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            part["part_number"],
            part["description"],
            part["category"],
            from_warehouse_id,
            to_warehouse_id,
            quantity,
            payload.get("notes", "").strip(),
            payload["transferredBy"].strip(),
            datetime.now().isoformat(),
        ),
    )
    db.commit()
    return jsonify(bootstrap_payload(from_warehouse_id))


@app.get("/api/export")
def api_export():
    warehouse_id = selected_warehouse_id()
    export_path = BASE_DIR / "instance" / "shopflow-export.json"
    export_path.write_text(json.dumps(bootstrap_payload(warehouse_id), indent=2), encoding="utf-8")
    return send_file(
        export_path,
        as_attachment=True,
        download_name=f"shopflow-export-{datetime.now().date().isoformat()}-{warehouse_id}.json",
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
