from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sqlite3
import statistics
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import app as shop_app


TARGETS_MS = {
    "home_load": 2000,
    "inventory_search": 2000,
    "job_pull": 2000,
    "job_edit": 2000,
    "po_create": 2000,
    "po_status": 2000,
    "po_receive": 2000,
    "job_complete": 2000,
    "dashboard_load": 3000,
    "insights_load": 5000,
    "ai_insights": 10000,
}

SCALE_PRESETS = {
    "smoke": {
        "warehouses": 3,
        "parts": 360,
        "vendors": 18,
        "active_jobs": 80,
        "completed_jobs": 220,
        "open_purchase_orders": 35,
        "historical_purchase_orders": 40,
        "workers": 12,
    },
    "medium": {
        "warehouses": 4,
        "parts": 3200,
        "vendors": 80,
        "active_jobs": 900,
        "completed_jobs": 4500,
        "open_purchase_orders": 320,
        "historical_purchase_orders": 220,
        "workers": 24,
    },
    "large": {
        "warehouses": 5,
        "parts": 4800,
        "vendors": 120,
        "active_jobs": 1500,
        "completed_jobs": 8000,
        "open_purchase_orders": 700,
        "historical_purchase_orders": 420,
        "workers": 36,
    },
}

PART_CATEGORIES = [
    "Tub Kits",
    "Shower Kits",
    "Drain Kits",
    "Trim Kits",
    "Wall Panels",
    "Adhesives",
    "Sealants",
    "Fasteners",
    "Glass",
    "Plumbing",
    "Accessories",
    "Warranty",
]

JOB_TYPES = [
    "Tub-to-Shower Conversion",
    "Shower Refresh",
    "Tub Install",
    "Acrylic Wall Upgrade",
    "Walk-In Shower",
    "Accessory Retrofit",
]

PART_DESCRIPTORS = [
    "Matte White",
    "Polished Chrome",
    "Brushed Nickel",
    "Almond",
    "60in",
    "72in",
    "Heavy Duty",
    "Quick-Set",
]

TECHNICIANS = [
    "Crew A",
    "Crew B",
    "Crew C",
    "Crew D",
    "Crew E",
    "Crew F",
    "Installer North",
    "Installer South",
    "Installer East",
    "Installer West",
]

ASK_INSIGHTS_QUESTION = "What parts are we running out of the fastest this week?"


@dataclass
class ActionResult:
    action: str
    ok: bool
    elapsed_ms: float
    status_code: int
    error: str = ""
    detail: str = ""
    scenario: str = ""


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * pct))))
    return ordered[index]


class StressHarness:
    def __init__(self, scale_name: str, seed: int, workers: int | None, keep_db: bool) -> None:
        self.scale_name = scale_name
        self.scale = dict(SCALE_PRESETS[scale_name])
        self.seed = seed
        self.random = random.Random(seed)
        self.workers = workers or int(self.scale["workers"])
        self.keep_db = keep_db
        self.results: list[ActionResult] = []
        self.scenario_summaries: list[dict] = []
        self.integrity_issues: list[dict] = []
        self.dataset_summary: dict[str, int | str | bool] = {}
        self.bottlenecks: list[str] = []
        self.recommendations: list[str] = []
        self.temp_dir = None
        self.original_db_path = shop_app.DB_PATH
        self.test_db_path: Path | None = None
        self.ai_enabled = bool(os.environ.get("OPENAI_API_KEY", "").strip())

    def run(self) -> dict:
        try:
            self.setup_isolated_database()
            self.seed_realistic_demo_data()
            self.capture_dataset_summary()
            self.run_scenarios()
            self.run_race_conditions()
            self.run_integrity_checks()
            report = self.build_report()
            self.write_report_files(report)
            return report
        finally:
            if self.keep_db and self.test_db_path:
                print(f"Stress-test database kept at: {self.test_db_path}")
            self.teardown()

    def setup_isolated_database(self) -> None:
        temp_root = Path(__file__).resolve().parent / "instance" / "stress_harness"
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        self.test_db_path = temp_root / "shopflow_stress.db"
        shop_app.DB_PATH = self.test_db_path
        shop_app.init_db()

    def teardown(self) -> None:
        shop_app.DB_PATH = self.original_db_path
        if self.test_db_path is not None and not self.keep_db:
            shutil.rmtree(self.test_db_path.parent, ignore_errors=True)

    def get_db(self) -> sqlite3.Connection:
        assert self.test_db_path is not None
        db = sqlite3.connect(self.test_db_path, timeout=30, check_same_thread=False)
        db.row_factory = sqlite3.Row
        return db

    def reset_all_data(self, db: sqlite3.Connection) -> None:
        db.execute("PRAGMA foreign_keys = OFF")
        tables = [
            "job_part_requirements",
            "jobs",
            "usage_logs",
            "receiving_logs",
            "purchase_order_lines",
            "purchase_orders",
            "order_list_items",
            "reorder_requests",
            "parts",
            "vendors",
            "order_form_templates",
            "stock_transfers",
            "warehouses",
        ]
        for table in tables:
            db.execute(f"DELETE FROM {table}")
        db.execute("DELETE FROM sqlite_sequence")
        db.execute("PRAGMA foreign_keys = ON")
        db.commit()

    def seed_realistic_demo_data(self) -> None:
        now = datetime.now()
        db = self.get_db()
        self.reset_all_data(db)

        templates = [
            ("BF-STD", "Bath Fitter Standard", "bathbuild"),
            ("BF-FAST", "Bath Fitter Fast Track", "bathbuild"),
            ("AQUA-GLS", "AquaFlow Glass", "aquaflow"),
            ("BULK", "Bulk Materials", "bathbuild"),
        ]
        for template_id, name, variant in templates:
            db.execute(
                """
                INSERT INTO order_form_templates (template_id, name, form_variant, notes, created_at, updated_at)
                VALUES (?, ?, ?, '', ?, ?)
                """,
                (template_id, name, variant, now.isoformat(), now.isoformat()),
            )

        warehouse_rows = []
        for index in range(int(self.scale["warehouses"])):
            name = f"Warehouse {index + 1}"
            code = f"WH{index + 1:02d}"
            cursor = db.execute(
                "INSERT INTO warehouses (name, code, is_active) VALUES (?, ?, 1)",
                (name, code),
            )
            warehouse_rows.append({"id": int(cursor.lastrowid), "name": name, "code": code})

        vendor_rows = []
        for index in range(int(self.scale["vendors"])):
            category = PART_CATEGORIES[index % len(PART_CATEGORIES)]
            vendor_name = f"{category.split()[0]} Supply {index + 1:03d}"
            contact = f"Planner {index + 1:03d}"
            email = f"vendor{index + 1:03d}@example.com"
            phone = f"555-01{index % 10}{(index // 10) % 10}-{1000 + index:04d}"
            lead_time = 2 + (index % 14)
            template_id = templates[index % len(templates)][0]
            cursor = db.execute(
                """
                INSERT INTO vendors (name, contact, email, phone, lead_time_days, linked_template_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (vendor_name, contact, email, phone, lead_time, template_id),
            )
            vendor_rows.append(
                {
                    "id": int(cursor.lastrowid),
                    "name": vendor_name,
                    "lead_time_days": lead_time,
                    "template_id": template_id,
                }
            )

        parts_by_warehouse: dict[int, list[dict]] = defaultdict(list)
        vendors_by_category = defaultdict(list)
        for vendor in vendor_rows:
            vendors_by_category[PART_CATEGORIES[(vendor["id"] - 1) % len(PART_CATEGORIES)]].append(vendor)

        total_parts = int(self.scale["parts"])
        for part_index in range(total_parts):
            warehouse = warehouse_rows[part_index % len(warehouse_rows)]
            category = PART_CATEGORIES[part_index % len(PART_CATEGORIES)]
            vendor_pool = vendors_by_category.get(category) or vendor_rows
            vendor = vendor_pool[part_index % len(vendor_pool)]
            descriptor = PART_DESCRIPTORS[part_index % len(PART_DESCRIPTORS)]
            item_type = "non_stock" if part_index % 7 == 0 else "stocked"
            reorder_point = 0 if item_type == "non_stock" else 4 + (part_index % 16)
            stock = 0 if item_type == "non_stock" else reorder_point + 4 + (part_index % 35)
            if item_type == "stocked" and part_index % 11 == 0:
                stock = max(0, reorder_point - (part_index % 3))
            part_number = f"{warehouse['code']}-{category[:3].upper()}-{part_index + 1:05d}"
            cursor = db.execute(
                """
                INSERT INTO parts (
                    warehouse_id, part_number, scan_code, description, category, item_type,
                    stock, reorder_point, vendor_id, unit_cost
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    warehouse["id"],
                    part_number,
                    part_number,
                    f"{descriptor} {category[:-1] if category.endswith('s') else category}",
                    category,
                    item_type,
                    stock,
                    reorder_point,
                    vendor["id"],
                    round(8 + ((part_index * 1.73) % 160), 2),
                ),
            )
            parts_by_warehouse[warehouse["id"]].append(
                {
                    "id": int(cursor.lastrowid),
                    "warehouse_id": warehouse["id"],
                    "warehouse_code": warehouse["code"],
                    "part_number": part_number,
                    "category": category,
                    "item_type": item_type,
                    "stock": stock,
                    "reorder_point": reorder_point,
                    "vendor_id": vendor["id"],
                    "vendor_name": vendor["name"],
                }
            )

        self.seed_jobs_and_usage(db, now, warehouse_rows, parts_by_warehouse)
        self.seed_purchase_orders(db, now, warehouse_rows, parts_by_warehouse, vendor_rows)
        self.seed_reorder_history(db, now, parts_by_warehouse, vendor_rows)

        db.commit()
        db.close()

    def seed_jobs_and_usage(
        self,
        db: sqlite3.Connection,
        now: datetime,
        warehouse_rows: list[dict],
        parts_by_warehouse: dict[int, list[dict]],
    ) -> None:
        job_counter = 1
        active_jobs = int(self.scale["active_jobs"])
        completed_jobs = int(self.scale["completed_jobs"])
        total_jobs = active_jobs + completed_jobs

        for job_index in range(total_jobs):
            warehouse = warehouse_rows[job_index % len(warehouse_rows)]
            is_completed = job_index >= active_jobs
            job_type = JOB_TYPES[job_index % len(JOB_TYPES)]
            technician = TECHNICIANS[job_index % len(TECHNICIANS)]
            created_days_ago = (job_index % 210) + (40 if is_completed else 0)
            created_at = now - timedelta(days=created_days_ago, hours=job_index % 12)
            status = "Completed" if is_completed else ("Ready to Go" if job_index % 5 == 0 else "Active")
            job_number = f"JOB-{created_at.year % 100:02d}-{job_counter:05d}"
            cursor = db.execute(
                """
                INSERT INTO jobs (
                    warehouse_id, job_number, title, customer_name, address, scheduled_for,
                    technician, status, notes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    warehouse["id"],
                    job_number,
                    job_type,
                    f"Customer {job_counter:05d}",
                    f"{100 + (job_counter % 900)} Main St",
                    (created_at + timedelta(days=2)).date().isoformat(),
                    technician,
                    status,
                    "Stress-test seeded job history",
                    created_at.isoformat(),
                ),
            )
            job_id = int(cursor.lastrowid)
            job_counter += 1

            preferred_categories = self.preferred_categories_for_job_type(job_type)
            part_pool = parts_by_warehouse[warehouse["id"]]
            job_parts = self.pick_parts_for_job(part_pool, preferred_categories, 4 + (job_index % 3))
            total_required = 0
            total_pulled = 0
            for req_index, part in enumerate(job_parts):
                required_quantity = 1 + ((job_index + req_index) % 4)
                pulled_quantity = required_quantity if is_completed or status == "Ready to Go" else max(0, required_quantity - ((req_index + job_index) % 3))
                total_required += required_quantity
                total_pulled += pulled_quantity
                db.execute(
                    """
                    INSERT INTO job_part_requirements (job_id, part_id, required_quantity, pulled_quantity, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (job_id, part["id"], required_quantity, pulled_quantity, created_at.isoformat()),
                )
                if pulled_quantity:
                    usage_date = created_at + timedelta(days=1 + (req_index % 2))
                    db.execute(
                        """
                        INSERT INTO usage_logs (warehouse_id, job_number, technician, part_id, quantity, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            warehouse["id"],
                            job_number,
                            technician,
                            part["id"],
                            pulled_quantity,
                            "Seeded job pull history",
                            usage_date.isoformat(),
                        ),
                    )
                if (job_index + req_index) % 17 == 0:
                    extra_qty = 1 + ((job_index + req_index) % 2)
                    db.execute(
                        """
                        INSERT INTO usage_logs (warehouse_id, job_number, technician, part_id, quantity, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            warehouse["id"],
                            job_number,
                            technician,
                            part["id"],
                            extra_qty,
                            "extra material usage on install",
                            (created_at + timedelta(days=2)).isoformat(),
                        ),
                    )

            if not is_completed and total_pulled >= total_required:
                db.execute("UPDATE jobs SET status = 'Ready to Go' WHERE id = ?", (job_id,))

        history_log_count = max(int(self.scale["parts"]) * 3, 2000)
        for history_index in range(history_log_count):
            warehouse = warehouse_rows[history_index % len(warehouse_rows)]
            part = parts_by_warehouse[warehouse["id"]][history_index % len(parts_by_warehouse[warehouse["id"]])]
            created_at = now - timedelta(days=1 + (history_index % 180), hours=history_index % 24)
            db.execute(
                """
                INSERT INTO usage_logs (warehouse_id, job_number, technician, part_id, quantity, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    warehouse["id"],
                    f"HIST-{warehouse['code']}-{history_index:05d}",
                    TECHNICIANS[history_index % len(TECHNICIANS)],
                    part["id"],
                    1 + (history_index % 4),
                    "Historical usage trend",
                    created_at.isoformat(),
                ),
            )

    def seed_purchase_orders(
        self,
        db: sqlite3.Connection,
        now: datetime,
        warehouse_rows: list[dict],
        parts_by_warehouse: dict[int, list[dict]],
        vendor_rows: list[dict],
    ) -> None:
        po_counter = 1
        total_open = int(self.scale["open_purchase_orders"])
        total_historical = int(self.scale["historical_purchase_orders"])
        total_pos = total_open + total_historical
        vendor_map = {vendor["id"]: vendor for vendor in vendor_rows}

        for po_index in range(total_pos):
            warehouse = warehouse_rows[po_index % len(warehouse_rows)]
            part_pool = parts_by_warehouse[warehouse["id"]]
            is_historical = po_index >= total_open
            created_at = now - timedelta(days=(po_index % 120) + (25 if is_historical else 1), hours=po_index % 11)
            line_count = 2 + (po_index % 5)
            lines = []
            chosen_parts = self.random.sample(part_pool, k=min(line_count, len(part_pool)))
            vendor = vendor_map[chosen_parts[0]["vendor_id"]]
            total_ordered = 0
            total_received = 0
            for line_index, part in enumerate(chosen_parts):
                ordered = 4 + ((po_index + line_index) % 22)
                if is_historical:
                    received = ordered
                elif po_index % 4 == 0:
                    received = max(0, ordered - (1 + (line_index % 3)))
                else:
                    received = 0
                total_ordered += ordered
                total_received += received
                lines.append((part, ordered, received))

            if total_received == 0:
                status = "Waiting for Part" if po_index % 3 else "Email Pending"
            elif total_received >= total_ordered:
                status = "Received"
            else:
                status = "Partial Received"

            cursor = db.execute(
                """
                INSERT INTO purchase_orders (
                    warehouse_id, po_number, vendor_id, template_id, eta, notes, status, created_at, updated_at,
                    part_id, quantity, received_quantity
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    warehouse["id"],
                    f"PO-{created_at.year % 100:02d}-{po_counter:05d}",
                    vendor["id"],
                    vendor["template_id"],
                    (created_at + timedelta(days=vendor["lead_time_days"])).date().isoformat(),
                    "Stress-test seeded purchase order",
                    status,
                    created_at.isoformat(),
                    created_at.isoformat(),
                    lines[0][0]["id"],
                    total_ordered,
                    total_received,
                ),
            )
            po_id = int(cursor.lastrowid)
            po_counter += 1

            for line_index, (part, ordered, received) in enumerate(lines):
                db.execute(
                    """
                    INSERT INTO purchase_order_lines (
                        purchase_order_id, part_id, quantity_ordered, quantity_received, notes, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        po_id,
                        part["id"],
                        ordered,
                        received,
                        "Seeded PO line",
                        created_at.isoformat(),
                        created_at.isoformat(),
                    ),
                )
                if received:
                    db.execute(
                        """
                        INSERT INTO receiving_logs (po_id, part_id, quantity, received_by, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            po_id,
                            part["id"],
                            received,
                            "Receiver Team",
                            f"Shipment {line_index + 1}",
                            (created_at + timedelta(days=1 + line_index)).isoformat(),
                        ),
                    )

    def seed_reorder_history(
        self,
        db: sqlite3.Connection,
        now: datetime,
        parts_by_warehouse: dict[int, list[dict]],
        vendor_rows: list[dict],
    ) -> None:
        vendor_map = {vendor["id"]: vendor for vendor in vendor_rows}
        reorder_count = max(180, int(self.scale["parts"]) // 8)
        flat_parts = [part for parts in parts_by_warehouse.values() for part in parts]
        for index in range(reorder_count):
            part = flat_parts[index % len(flat_parts)]
            vendor = vendor_map[part["vendor_id"]]
            created_at = now - timedelta(days=index % 90, hours=index % 8)
            db.execute(
                """
                INSERT INTO reorder_requests (warehouse_id, part_id, vendor_id, quantity, reason, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    part["warehouse_id"],
                    part["id"],
                    vendor["id"],
                    4 + (index % 20),
                    "Historical reorder signal",
                    "Sent to PO" if index % 3 else "Form Ready",
                    created_at.isoformat(),
                ),
            )

    def preferred_categories_for_job_type(self, job_type: str) -> list[str]:
        mapping = {
            "Tub-to-Shower Conversion": ["Drain Kits", "Trim Kits", "Wall Panels", "Sealants"],
            "Shower Refresh": ["Shower Kits", "Glass", "Trim Kits", "Sealants"],
            "Tub Install": ["Tub Kits", "Drain Kits", "Plumbing", "Fasteners"],
            "Acrylic Wall Upgrade": ["Wall Panels", "Adhesives", "Sealants", "Accessories"],
            "Walk-In Shower": ["Glass", "Trim Kits", "Shower Kits", "Accessories"],
            "Accessory Retrofit": ["Accessories", "Fasteners", "Sealants", "Warranty"],
        }
        return mapping.get(job_type, PART_CATEGORIES[:4])

    def pick_parts_for_job(self, part_pool: list[dict], preferred_categories: list[str], count: int) -> list[dict]:
        preferred = [part for part in part_pool if part["category"] in preferred_categories]
        fallback = preferred if len(preferred) >= count else part_pool
        return self.random.sample(fallback, k=min(count, len(fallback)))

    def capture_dataset_summary(self) -> None:
        db = self.get_db()
        counts = {
            "parts": db.execute("SELECT COUNT(*) AS count FROM parts").fetchone()["count"],
            "vendors": db.execute("SELECT COUNT(*) AS count FROM vendors").fetchone()["count"],
            "active_jobs": db.execute("SELECT COUNT(*) AS count FROM jobs WHERE status != 'Completed'").fetchone()["count"],
            "completed_jobs": db.execute("SELECT COUNT(*) AS count FROM jobs WHERE status = 'Completed'").fetchone()["count"],
            "open_purchase_orders": db.execute("SELECT COUNT(*) AS count FROM purchase_orders WHERE status != 'Received'").fetchone()["count"],
            "historical_purchase_orders": db.execute("SELECT COUNT(*) AS count FROM purchase_orders WHERE status = 'Received'").fetchone()["count"],
            "usage_logs": db.execute("SELECT COUNT(*) AS count FROM usage_logs").fetchone()["count"],
            "receiving_logs": db.execute("SELECT COUNT(*) AS count FROM receiving_logs").fetchone()["count"],
            "non_stock_parts": db.execute("SELECT COUNT(*) AS count FROM parts WHERE item_type = 'non_stock'").fetchone()["count"],
            "warehouses": db.execute("SELECT COUNT(*) AS count FROM warehouses").fetchone()["count"],
        }
        db.close()
        self.dataset_summary = {key: int(value) for key, value in counts.items()}
        self.dataset_summary["scale"] = self.scale_name
        self.dataset_summary["ai_enabled"] = self.ai_enabled

    def client(self):
        return shop_app.app.test_client()

    def db_row(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        db = self.get_db()
        row = db.execute(query, params).fetchone()
        db.close()
        return row

    def db_rows(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        db = self.get_db()
        rows = db.execute(query, params).fetchall()
        db.close()
        return rows

    def timed_action(self, action: str, scenario: str, fn) -> ActionResult:
        started = time.perf_counter()
        try:
            status_code, detail = fn()
            elapsed_ms = (time.perf_counter() - started) * 1000
            ok = 200 <= status_code < 300
            error = "" if ok else detail
            return ActionResult(action, ok, elapsed_ms, status_code, error=error, detail=detail, scenario=scenario)
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = (time.perf_counter() - started) * 1000
            return ActionResult(action, False, elapsed_ms, 500, error=str(exc), detail=str(exc), scenario=scenario)

    def run_concurrent_scenario(self, name: str, factories: list) -> None:
        scenario_results: list[ActionResult] = []
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = [executor.submit(factory) for factory in factories]
            for future in as_completed(futures):
                result = future.result()
                scenario_results.append(result)
                self.results.append(result)
        action_failures = [result for result in scenario_results if not result.ok]
        self.scenario_summaries.append(
            {
                "name": name,
                "total_actions": len(scenario_results),
                "failures": len(action_failures),
                "passed": len(action_failures) == 0,
                "avg_ms": round(statistics.mean([result.elapsed_ms for result in scenario_results]), 2) if scenario_results else 0,
            }
        )

    def run_scenarios(self) -> None:
        self.run_concurrent_scenario(
            "Morning Rush",
            [self.make_task(self.random.choice([self.action_load_home, self.action_load_dashboard, self.action_search_inventory, self.action_pull_part, self.action_edit_job, self.action_load_insights]), "Morning Rush") for _ in range(70)],
        )
        self.run_concurrent_scenario(
            "Large Receiving Session",
            [self.make_task(self.random.choice([self.action_receive_po, self.action_receive_po, self.action_po_status, self.action_create_po]), "Large Receiving Session") for _ in range(55)],
        )
        self.run_concurrent_scenario(
            "Heavy Job Pulling",
            [self.make_task(self.random.choice([self.action_pull_part, self.action_pull_part, self.action_edit_job]), "Heavy Job Pulling") for _ in range(65)],
        )
        mixed_dashboard_tasks = [self.make_task(self.random.choice([self.action_load_home, self.action_load_dashboard, self.action_load_insights, self.action_search_inventory]), "Dashboard + Insights During Updates") for _ in range(35)]
        mixed_dashboard_tasks.extend([self.make_task(self.random.choice([self.action_pull_part, self.action_receive_po, self.action_edit_job]), "Dashboard + Insights During Updates") for _ in range(35)])
        if self.ai_enabled:
            mixed_dashboard_tasks.extend([self.make_task(self.action_ai_insights, "Dashboard + Insights During Updates") for _ in range(8)])
        self.run_concurrent_scenario("Dashboard + Insights During Updates", mixed_dashboard_tasks)
        self.run_concurrent_scenario(
            "End of Day Closeout",
            [self.make_task(self.random.choice([self.action_complete_job, self.action_edit_job, self.action_load_dashboard, self.action_create_po]), "End of Day Closeout") for _ in range(45)],
        )

    def make_task(self, action_fn, scenario: str):
        return lambda: action_fn(scenario)

    def action_load_home(self, scenario: str) -> ActionResult:
        return self.timed_action("home_load", scenario, lambda: self.simple_get("/"))

    def simple_get(self, path: str) -> tuple[int, str]:
        client = self.client()
        response = client.get(path)
        return response.status_code, ""

    def random_warehouse_id(self) -> int:
        row = self.db_row("SELECT id FROM warehouses ORDER BY RANDOM() LIMIT 1")
        return int(row["id"]) if row else 1

    def action_load_dashboard(self, scenario: str) -> ActionResult:
        warehouse_id = self.random_warehouse_id()
        return self.timed_action("dashboard_load", scenario, lambda: self.bootstrap_and_touch(warehouse_id, touch="dashboard"))

    def action_load_insights(self, scenario: str) -> ActionResult:
        warehouse_id = self.random_warehouse_id()
        return self.timed_action("insights_load", scenario, lambda: self.bootstrap_and_touch(warehouse_id, touch="insights"))

    def bootstrap_and_touch(self, warehouse_id: int, touch: str) -> tuple[int, str]:
        client = self.client()
        response = client.get(f"/api/bootstrap?warehouseId={warehouse_id}")
        if response.status_code != 200:
            return response.status_code, response.get_json(silent=True).get("error", "bootstrap failed") if response.is_json else "bootstrap failed"
        payload = response.get_json()
        if touch == "dashboard":
            _ = len(payload.get("parts", [])) + len(payload.get("jobs", [])) + len(payload.get("purchaseOrders", []))
        else:
            usage_by_month: dict[str, int] = defaultdict(int)
            for log in payload.get("usageLogs", [])[:4000]:
                usage_by_month[str(log.get("created_at") or "")[:7]] += int(log.get("quantity") or 0)
            _ = sorted(usage_by_month.items())[:12]
        return response.status_code, ""

    def action_search_inventory(self, scenario: str) -> ActionResult:
        warehouse_id = self.random_warehouse_id()
        return self.timed_action("inventory_search", scenario, lambda: self.search_inventory_payload(warehouse_id))

    def search_inventory_payload(self, warehouse_id: int) -> tuple[int, str]:
        client = self.client()
        response = client.get(f"/api/bootstrap?warehouseId={warehouse_id}")
        if response.status_code != 200:
            return response.status_code, "bootstrap failed"
        payload = response.get_json()
        sample_part = payload.get("parts", [])[self.random.randrange(len(payload.get("parts", [])))] if payload.get("parts") else {}
        source_text = str(sample_part.get("part_number") or sample_part.get("description") or "KIT").upper()
        term = source_text[: max(3, min(6, len(source_text)))]
        matches = [
            part["part_number"]
            for part in payload.get("parts", [])
            if term in str(part.get("part_number", "")).upper() or term in str(part.get("description", "")).upper()
        ]
        if not matches:
            return 500, "search returned no matches unexpectedly"
        return 200, ""

    def action_pull_part(self, scenario: str) -> ActionResult:
        return self.timed_action("job_pull", scenario, self.pull_random_requirement)

    def pull_random_requirement(self) -> tuple[int, str]:
        row = self.db_row(
            """
            SELECT req.id, jobs.warehouse_id, req.required_quantity, req.pulled_quantity, parts.stock
            FROM job_part_requirements req
            JOIN jobs ON jobs.id = req.job_id
            JOIN parts ON parts.id = req.part_id
            WHERE jobs.status != 'Completed'
              AND parts.item_type = 'stocked'
              AND req.required_quantity > req.pulled_quantity
              AND parts.stock > 0
            ORDER BY RANDOM()
            LIMIT 1
            """
        )
        if row is None:
            return 409, "no pullable requirement available"
        remaining = int(row["required_quantity"]) - int(row["pulled_quantity"])
        quantity = max(1, min(2, remaining, int(row["stock"])))
        client = self.client()
        response = client.post(
            f"/api/job-parts/{int(row['id'])}/pull",
            json={"warehouseId": int(row["warehouse_id"]), "quantity": quantity, "notes": "stress pull"},
        )
        if response.status_code >= 400:
            error_message = (response.get_json(silent=True) or {}).get("error", "pull failed")
            if error_message.startswith("Only 0 part(s) remain") or error_message == "Not enough inventory on hand for that pull.":
                return 200, f"safe_conflict:{error_message}"
            return response.status_code, error_message
        return response.status_code, ""

    def action_edit_job(self, scenario: str) -> ActionResult:
        return self.timed_action("job_edit", scenario, self.edit_random_job)

    def edit_random_job(self) -> tuple[int, str]:
        job = self.db_row("SELECT * FROM jobs WHERE status != 'Completed' ORDER BY RANDOM() LIMIT 1")
        if job is None:
            return 409, "no editable job"
        requirements = self.db_rows("SELECT id, required_quantity FROM job_part_requirements WHERE job_id = ? ORDER BY id", (int(job["id"]),))
        client = self.client()
        response = client.post(
            f"/api/jobs/{int(job['id'])}",
            json={
                "warehouseId": int(job["warehouse_id"]),
                "jobNumber": job["job_number"],
                "title": job["title"],
                "customerName": job["customer_name"],
                "address": job["address"],
                "scheduledFor": job["scheduled_for"],
                "technician": job["technician"],
                "notes": f"{job['notes']} | stress edit {int(time.time() * 1000) % 100000}",
                "requirementQuantities": [{"requirementId": int(req["id"]), "requiredQuantity": int(req["required_quantity"])} for req in requirements],
            },
        )
        if response.status_code >= 400:
            return response.status_code, (response.get_json(silent=True) or {}).get("error", "job edit failed")
        return response.status_code, ""

    def action_create_po(self, scenario: str) -> ActionResult:
        return self.timed_action("po_create", scenario, self.create_random_po)

    def create_random_po(self) -> tuple[int, str]:
        part = self.db_row(
            """
            SELECT id, warehouse_id, vendor_id
            FROM parts
            WHERE item_type = 'stocked'
            ORDER BY RANDOM()
            LIMIT 1
            """
        )
        if part is None:
            return 409, "no stocked part for PO"
        client = self.client()
        response = client.post(
            "/api/purchase-orders",
            json={
                "warehouseId": int(part["warehouse_id"]),
                "vendorId": int(part["vendor_id"]),
                "partId": int(part["id"]),
                "quantity": 6 + (int(part["id"]) % 8),
                "eta": (datetime.now() + timedelta(days=5)).date().isoformat(),
                "notes": "stress-created po",
            },
        )
        if response.status_code >= 400:
            return response.status_code, (response.get_json(silent=True) or {}).get("error", "po create failed")
        return response.status_code, ""

    def action_po_status(self, scenario: str) -> ActionResult:
        return self.timed_action("po_status", scenario, self.update_random_po_status)

    def update_random_po_status(self) -> tuple[int, str]:
        po = self.db_row(
            """
            SELECT id, warehouse_id, status
            FROM purchase_orders
            WHERE status != 'Received'
            ORDER BY RANDOM()
            LIMIT 1
            """
        )
        if po is None:
            return 409, "no open po"
        next_status = "Waiting for Part" if po["status"] == "Email Pending" else "Partial Received"
        client = self.client()
        response = client.post(
            f"/api/purchase-orders/{int(po['id'])}/status",
            json={"warehouseId": int(po["warehouse_id"]), "status": next_status},
        )
        if response.status_code >= 400:
            return response.status_code, (response.get_json(silent=True) or {}).get("error", "po status failed")
        return response.status_code, ""

    def action_receive_po(self, scenario: str) -> ActionResult:
        return self.timed_action("po_receive", scenario, self.receive_random_po)

    def receive_random_po(self) -> tuple[int, str]:
        po = self.db_row(
            """
            SELECT id, warehouse_id
            FROM purchase_orders
            WHERE status IN ('Email Pending', 'Waiting for Part', 'Partial Received')
            ORDER BY RANDOM()
            LIMIT 1
            """
        )
        if po is None:
            return 409, "no receivable po"
        lines = self.db_rows(
            """
            SELECT id, quantity_ordered, quantity_received
            FROM purchase_order_lines
            WHERE purchase_order_id = ?
            ORDER BY id
            """,
            (int(po["id"]),),
        )
        if not lines:
            return 409, "po has no lines"
        line_receipts: dict[str, int] = {}
        line_verifications: dict[str, bool] = {}
        touched = 0
        for line in lines:
            outstanding = max(int(line["quantity_ordered"]) - int(line["quantity_received"]), 0)
            if outstanding <= 0:
                continue
            if touched < 2:
                quantity = max(1, min(outstanding, 1 + (int(line["id"]) % 3)))
                line_receipts[str(int(line["id"]))] = quantity
                line_verifications[str(int(line["id"]))] = True
                touched += 1
            else:
                line_receipts[str(int(line["id"]))] = 0
                line_verifications[str(int(line["id"]))] = False
        if touched == 0:
            return 409, "po already fully received"
        client = self.client()
        response = client.post(
            f"/api/purchase-orders/{int(po['id'])}/receive",
            json={
                "warehouseId": int(po["warehouse_id"]),
                "lineReceipts": line_receipts,
                "lineVerifications": line_verifications,
                "allowOverage": False,
                "receivedBy": "Stress Harness",
                "notes": "stress partial receipt",
            },
        )
        if response.status_code >= 400:
            error_message = (response.get_json(silent=True) or {}).get("error", "po receive failed")
            if "cannot receive more than the outstanding quantity without confirmation" in error_message:
                return 200, f"safe_conflict:{error_message}"
            return response.status_code, error_message
        return response.status_code, ""

    def action_complete_job(self, scenario: str) -> ActionResult:
        return self.timed_action("job_complete", scenario, self.complete_random_job)

    def complete_random_job(self) -> tuple[int, str]:
        job = self.db_row(
            """
            SELECT id, warehouse_id
            FROM jobs
            WHERE status = 'Ready to Go'
            ORDER BY RANDOM()
            LIMIT 1
            """
        )
        if job is None:
            return 409, "no ready job"
        client = self.client()
        response = client.post(
            f"/api/jobs/{int(job['id'])}/complete",
            json={"warehouseId": int(job["warehouse_id"]), "notes": "stress closeout"},
        )
        if response.status_code >= 400:
            return response.status_code, (response.get_json(silent=True) or {}).get("error", "job complete failed")
        return response.status_code, ""

    def action_ai_insights(self, scenario: str) -> ActionResult:
        return self.timed_action("ai_insights", scenario, self.ask_ai_insights)

    def ask_ai_insights(self) -> tuple[int, str]:
        if not self.ai_enabled:
            return 204, "OPENAI_API_KEY not configured"
        warehouse_id = self.random_warehouse_id()
        client = self.client()
        bootstrap = client.get(f"/api/bootstrap?warehouseId={warehouse_id}")
        if bootstrap.status_code != 200:
            return bootstrap.status_code, "bootstrap failed"
        payload = bootstrap.get_json()
        context = self.build_ai_context(payload, warehouse_id)
        response = client.post(
            "/api/insights/ask",
            json={"mode": "query", "question": ASK_INSIGHTS_QUESTION, "context": context},
        )
        if response.status_code >= 400:
            return response.status_code, (response.get_json(silent=True) or {}).get("error", "ai insights failed")
        return response.status_code, ""

    def build_ai_context(self, payload: dict, warehouse_id: int) -> dict:
        usage_logs = payload.get("usageLogs", [])
        parts = payload.get("parts", [])
        jobs = payload.get("jobs", [])
        completed_jobs = payload.get("completedJobs", [])
        part_usage = Counter()
        for log in usage_logs[:2000]:
            if int(log.get("quantity") or 0) > 0:
                part_usage[str(log.get("part_number"))] += int(log.get("quantity") or 0)
        top_parts = part_usage.most_common(8)
        reorder = []
        for part in parts[:300]:
            stock = int(part.get("stock") or 0)
            reorder_point = int(part.get("reorder_point") or 0)
            if part.get("item_type") == "stocked" and stock <= reorder_point + 5:
                reorder.append(
                    {
                        "partNumber": part.get("part_number"),
                        "stock": stock,
                        "reorderPoint": reorder_point,
                        "daysUntilReorder": 3 + (stock % 9),
                    }
                )
        return {
            "scope": {
                "filters": {"warehouseId": warehouse_id, "dateRangeDays": 60},
                "dateRangeDays": 60,
                "jobsAnalyzed": len(jobs) + len(completed_jobs),
                "usageLogsAnalyzed": len(usage_logs),
                "sampling": {"mode": "sampled", "usedFullFilteredRecords": False},
            },
            "allowedPartIds": [int(part["id"]) for part in parts[:300]],
            "metricsCatalog": [
                {"key": "top_parts", "label": "Top moving parts", "value": ", ".join(part for part, _qty in top_parts[:3]) or "None"},
                {"key": "active_jobs", "label": "Active jobs", "value": str(len(jobs))},
                {"key": "completed_jobs", "label": "Completed jobs", "value": str(len(completed_jobs))},
            ],
            "reorder": reorder[:10],
            "mostUsedParts": [{"partNumber": part, "quantity": qty} for part, qty in top_parts],
            "anomalies": [],
            "summaries": [],
        }

    def run_race_conditions(self) -> None:
        self.race_pull_same_inventory_item()
        self.race_receive_same_purchase_order()
        self.race_edit_same_job()
        self.race_edit_same_part_stock()
        self.verification_is_per_line_test()

    def race_pull_same_inventory_item(self) -> None:
        db = self.get_db()
        warehouse = db.execute("SELECT id, code FROM warehouses ORDER BY id LIMIT 1").fetchone()
        vendor = db.execute("SELECT id FROM vendors ORDER BY id LIMIT 1").fetchone()
        timestamp = datetime.now().isoformat()
        part_cursor = db.execute(
            """
            INSERT INTO parts (warehouse_id, part_number, scan_code, description, category, item_type, stock, reorder_point, vendor_id, unit_cost)
            VALUES (?, ?, ?, 'Race pull part', 'Drain Kits', 'stocked', 8, 2, ?, 18.5)
            """,
            (int(warehouse["id"]), f"{warehouse['code']}-RACE-PULL", f"{warehouse['code']}-RACE-PULL", int(vendor["id"])),
        )
        part_id = int(part_cursor.lastrowid)
        requirement_ids = []
        for index in range(2):
            job_cursor = db.execute(
                """
                INSERT INTO jobs (warehouse_id, job_number, title, customer_name, address, scheduled_for, technician, status, notes, created_at)
                VALUES (?, ?, 'Race Pull Job', 'Race Customer', '1 Race Way', ?, ?, 'Active', 'race pull test', ?)
                """,
                (int(warehouse["id"]), f"RACE-PULL-{index + 1}", datetime.now().date().isoformat(), TECHNICIANS[index], timestamp),
            )
            job_id = int(job_cursor.lastrowid)
            req_cursor = db.execute(
                """
                INSERT INTO job_part_requirements (job_id, part_id, required_quantity, pulled_quantity, created_at)
                VALUES (?, ?, 6, 0, ?)
                """,
                (job_id, part_id, timestamp),
            )
            requirement_ids.append(int(req_cursor.lastrowid))
        db.commit()
        db.close()

        barrier = threading.Barrier(2)
        scenario = "Race: Pull Same Inventory Item"

        def worker(requirement_id: int) -> ActionResult:
            return self.timed_action(
                "job_pull",
                scenario,
                lambda: self.concurrent_request(barrier, f"/api/job-parts/{requirement_id}/pull", {"warehouseId": int(warehouse["id"]), "quantity": 6, "notes": "race pull"}),
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            race_results = [future.result() for future in as_completed([executor.submit(worker, req_id) for req_id in requirement_ids])]
        self.results.extend(race_results)
        stock_row = self.db_row("SELECT stock FROM parts WHERE id = ?", (part_id,))
        pulled_total = self.db_row("SELECT COALESCE(SUM(pulled_quantity), 0) AS total FROM job_part_requirements WHERE part_id = ?", (part_id,))
        if stock_row and int(stock_row["stock"]) < 0:
            self.integrity_issues.append({"check": scenario, "severity": "high", "message": f"Concurrent pulls drove stock negative to {int(stock_row['stock'])}."})
        elif pulled_total and int(pulled_total["total"]) > 8:
            self.integrity_issues.append({"check": scenario, "severity": "high", "message": f"Concurrent pulls allocated {int(pulled_total['total'])} units against only 8 on hand."})

    def race_receive_same_purchase_order(self) -> None:
        db = self.get_db()
        warehouse = db.execute("SELECT id, code FROM warehouses ORDER BY id LIMIT 1").fetchone()
        part = db.execute("SELECT id, vendor_id FROM parts WHERE warehouse_id = ? AND item_type = 'stocked' ORDER BY id LIMIT 1", (int(warehouse["id"]),)).fetchone()
        timestamp = datetime.now().isoformat()
        po_cursor = db.execute(
            """
            INSERT INTO purchase_orders (
                warehouse_id, po_number, vendor_id, template_id, eta, notes, status, created_at, updated_at, part_id, quantity, received_quantity
            )
            VALUES (?, ?, ?, 'BF-STD', ?, 'race receive', 'Waiting for Part', ?, ?, ?, 10, 0)
            """,
            (int(warehouse["id"]), f"RACE-PO-{int(time.time()) % 100000}", int(part["vendor_id"]), datetime.now().date().isoformat(), timestamp, timestamp, int(part["id"])),
        )
        po_id = int(po_cursor.lastrowid)
        line_cursor = db.execute(
            """
            INSERT INTO purchase_order_lines (
                purchase_order_id, part_id, quantity_ordered, quantity_received, notes, created_at, updated_at
            )
            VALUES (?, ?, 10, 0, 'race line', ?, ?)
            """,
            (po_id, int(part["id"]), timestamp, timestamp),
        )
        line_id = int(line_cursor.lastrowid)
        db.commit()
        db.close()

        barrier = threading.Barrier(2)
        scenario = "Race: Receive Same Purchase Order"

        def worker() -> ActionResult:
            return self.timed_action(
                "po_receive",
                scenario,
                lambda: self.concurrent_request(
                    barrier,
                    f"/api/purchase-orders/{po_id}/receive",
                    {
                        "warehouseId": int(warehouse["id"]),
                        "lineReceipts": {str(line_id): 7},
                        "lineVerifications": {str(line_id): True},
                        "allowOverage": False,
                        "receivedBy": "Race Harness",
                        "notes": "race receive",
                    },
                ),
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            race_results = [future.result() for future in as_completed([executor.submit(worker) for _ in range(2)])]
        self.results.extend(race_results)
        line = self.db_row("SELECT quantity_ordered, quantity_received FROM purchase_order_lines WHERE id = ?", (line_id,))
        if line and int(line["quantity_received"]) > int(line["quantity_ordered"]):
            self.integrity_issues.append({"check": scenario, "severity": "high", "message": f"Concurrent receiving recorded {int(line['quantity_received'])} against only {int(line['quantity_ordered'])} ordered."})

    def race_edit_same_job(self) -> None:
        job = self.db_row("SELECT * FROM jobs WHERE status != 'Completed' ORDER BY RANDOM() LIMIT 1")
        if job is None:
            return
        requirements = self.db_rows("SELECT id, required_quantity FROM job_part_requirements WHERE job_id = ? ORDER BY id", (int(job["id"]),))
        barrier = threading.Barrier(2)
        scenario = "Race: Edit Same Job"

        def worker(note_text: str) -> ActionResult:
            return self.timed_action(
                "job_edit",
                scenario,
                lambda: self.concurrent_request(
                    barrier,
                    f"/api/jobs/{int(job['id'])}",
                    {
                        "warehouseId": int(job["warehouse_id"]),
                        "jobNumber": job["job_number"],
                        "title": job["title"],
                        "customerName": job["customer_name"],
                        "address": job["address"],
                        "scheduledFor": job["scheduled_for"],
                        "technician": job["technician"],
                        "notes": note_text,
                        "requirementQuantities": [{"requirementId": int(req["id"]), "requiredQuantity": int(req["required_quantity"])} for req in requirements],
                    },
                ),
            )

        note_a = "race note A"
        note_b = "race note B"
        with ThreadPoolExecutor(max_workers=2) as executor:
            race_results = [future.result() for future in as_completed([executor.submit(worker, note_a), executor.submit(worker, note_b)])]
        self.results.extend(race_results)
        current = self.db_row("SELECT notes FROM jobs WHERE id = ?", (int(job["id"]),))
        successful = [result for result in race_results if result.ok]
        if len(successful) == 2 and current and current["notes"] in {note_a, note_b}:
            self.integrity_issues.append({"check": scenario, "severity": "medium", "message": "Two concurrent job edits both succeeded and one silently overwrote the other with no conflict signal."})

    def race_edit_same_part_stock(self) -> None:
        part = self.db_row("SELECT * FROM parts WHERE item_type = 'stocked' ORDER BY RANDOM() LIMIT 1")
        if part is None:
            return
        barrier = threading.Barrier(2)
        scenario = "Race: Edit Same Part Quantity"

        def worker(new_stock: int) -> ActionResult:
            return self.timed_action(
                "job_edit",
                scenario,
                lambda: self.concurrent_request(
                    barrier,
                    "/api/parts",
                    {
                        "id": int(part["id"]),
                        "warehouseId": int(part["warehouse_id"]),
                        "partNumber": part["part_number"],
                        "scanCode": part["scan_code"],
                        "description": part["description"],
                        "category": part["category"],
                        "itemType": part["item_type"],
                        "stock": new_stock,
                        "reorderPoint": int(part["reorder_point"]),
                        "vendorId": int(part["vendor_id"]),
                        "unitCost": float(part["unit_cost"]),
                    },
                ),
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            race_results = [future.result() for future in as_completed([executor.submit(worker, 9), executor.submit(worker, 27)])]
        self.results.extend(race_results)
        current = self.db_row("SELECT stock FROM parts WHERE id = ?", (int(part["id"]),))
        successful = [result for result in race_results if result.ok]
        if len(successful) == 2 and current and int(current["stock"]) in {9, 27}:
            self.integrity_issues.append({"check": scenario, "severity": "medium", "message": "Two concurrent part-stock edits both succeeded and one silently overwrote the other."})

    def verification_is_per_line_test(self) -> None:
        db = self.get_db()
        warehouse = db.execute("SELECT id FROM warehouses ORDER BY id LIMIT 1").fetchone()
        parts = db.execute("SELECT id, vendor_id FROM parts WHERE warehouse_id = ? AND item_type = 'stocked' ORDER BY id LIMIT 2", (int(warehouse["id"]),)).fetchall()
        timestamp = datetime.now().isoformat()
        po_cursor = db.execute(
            """
            INSERT INTO purchase_orders (
                warehouse_id, po_number, vendor_id, template_id, eta, notes, status, created_at, updated_at, part_id, quantity, received_quantity
            )
            VALUES (?, ?, ?, 'BF-STD', ?, 'verification leak test', 'Waiting for Part', ?, ?, ?, 8, 0)
            """,
            (int(warehouse["id"]), f"VERIFY-{int(time.time()) % 100000}", int(parts[0]["vendor_id"]), datetime.now().date().isoformat(), timestamp, timestamp, int(parts[0]["id"])),
        )
        po_id = int(po_cursor.lastrowid)
        line_ids = []
        for part in parts:
            line_cursor = db.execute(
                """
                INSERT INTO purchase_order_lines (
                    purchase_order_id, part_id, quantity_ordered, quantity_received, notes, created_at, updated_at
                )
                VALUES (?, ?, 4, 0, 'verification line', ?, ?)
                """,
                (po_id, int(part["id"]), timestamp, timestamp),
            )
            line_ids.append(int(line_cursor.lastrowid))
        db.commit()
        db.close()

        client = self.client()
        response = client.post(
            f"/api/purchase-orders/{po_id}/receive",
            json={
                "warehouseId": int(warehouse["id"]),
                "lineReceipts": {str(line_ids[0]): 2, str(line_ids[1]): 0},
                "lineVerifications": {str(line_ids[0]): True, str(line_ids[1]): False},
                "allowOverage": False,
                "receivedBy": "Verification Harness",
                "notes": "line verification check",
            },
        )
        self.results.append(ActionResult(action="po_receive", ok=response.status_code == 200, elapsed_ms=0, status_code=response.status_code, error="" if response.status_code == 200 else (response.get_json(silent=True) or {}).get("error", "verification test failed"), detail="verification leak test", scenario="Verification Isolation"))
        lines = self.db_rows("SELECT id, quantity_received FROM purchase_order_lines WHERE purchase_order_id = ? ORDER BY id", (po_id,))
        if len(lines) == 2 and int(lines[0]["quantity_received"]) == 2 and int(lines[1]["quantity_received"]) == 0:
            return
        self.integrity_issues.append({"check": "Verification Isolation", "severity": "high", "message": "Per-line visual verification leaked across purchase-order lines."})

    def concurrent_request(self, barrier: threading.Barrier, path: str, payload: dict) -> tuple[int, str]:
        client = self.client()
        barrier.wait(timeout=5)
        response = client.post(path, json=payload)
        if response.status_code >= 400:
            return response.status_code, (response.get_json(silent=True) or {}).get("error", response.status)
        return response.status_code, ""

    def run_integrity_checks(self) -> None:
        db = self.get_db()
        checks = [
            ("Negative stock", "SELECT COUNT(*) AS count FROM parts WHERE stock < 0", "Inventory contains negative on-hand stock.", "high"),
            (
                "Duplicate part numbers",
                """
                SELECT COUNT(*) AS count
                FROM (
                    SELECT warehouse_id, part_number
                    FROM parts
                    GROUP BY warehouse_id, part_number
                    HAVING COUNT(*) > 1
                )
                """,
                "Duplicate part numbers exist within the same warehouse.",
                "high",
            ),
            (
                "Duplicate scan codes",
                """
                SELECT COUNT(*) AS count
                FROM (
                    SELECT warehouse_id, scan_code
                    FROM parts
                    WHERE TRIM(scan_code) != ''
                    GROUP BY warehouse_id, scan_code
                    HAVING COUNT(*) > 1
                )
                """,
                "Duplicate scan codes exist within the same warehouse.",
                "high",
            ),
            (
                "Duplicate PO numbers",
                """
                SELECT COUNT(*) AS count
                FROM (
                    SELECT po_number
                    FROM purchase_orders
                    GROUP BY po_number
                    HAVING COUNT(*) > 1
                )
                """,
                "Duplicate purchase-order numbers exist.",
                "high",
            ),
            (
                "Orphan job requirements",
                """
                SELECT COUNT(*) AS count
                FROM job_part_requirements req
                LEFT JOIN jobs ON jobs.id = req.job_id
                LEFT JOIN parts ON parts.id = req.part_id
                WHERE jobs.id IS NULL OR parts.id IS NULL
                """,
                "Job-part assignments have orphaned references.",
                "high",
            ),
        ]
        for name, query, message, severity in checks:
            count = int(db.execute(query).fetchone()["count"])
            if count:
                self.integrity_issues.append({"check": name, "severity": severity, "message": f"{message} Count: {count}."})

        po_log_mismatch = db.execute(
            """
            SELECT COUNT(*) AS count
            FROM (
                SELECT lines.id
                FROM purchase_order_lines lines
                LEFT JOIN (
                    SELECT po_id, part_id, SUM(quantity) AS total_received
                    FROM receiving_logs
                    GROUP BY po_id, part_id
                ) logs
                    ON logs.po_id = lines.purchase_order_id AND logs.part_id = lines.part_id
                WHERE COALESCE(logs.total_received, 0) < lines.quantity_received
            )
            """
        ).fetchone()
        if int(po_log_mismatch["count"]):
            self.integrity_issues.append({"check": "Receiving accuracy", "severity": "high", "message": "Some purchase-order line totals exceed their receiving log totals."})

        warehouse = db.execute("SELECT id FROM warehouses ORDER BY id LIMIT 1").fetchone()
        db.close()
        if warehouse:
            client = self.client()
            response = client.get(f"/api/bootstrap?warehouseId={int(warehouse['id'])}")
            if response.status_code == 200:
                payload = response.get_json()
                db = self.get_db()
                expected_active = int(db.execute("SELECT COUNT(*) AS count FROM jobs WHERE warehouse_id = ? AND status != 'Completed'", (int(warehouse["id"]),)).fetchone()["count"])
                expected_completed = int(db.execute("SELECT COUNT(*) AS count FROM jobs WHERE warehouse_id = ? AND status = 'Completed'", (int(warehouse["id"]),)).fetchone()["count"])
                expected_parts = int(db.execute("SELECT COUNT(*) AS count FROM parts WHERE warehouse_id = ?", (int(warehouse["id"]),)).fetchone()["count"])
                expected_pos = int(db.execute("SELECT COUNT(*) AS count FROM purchase_orders WHERE warehouse_id = ?", (int(warehouse["id"]),)).fetchone()["count"])
                db.close()
                mismatches = []
                if len(payload.get("jobs", [])) != expected_active:
                    mismatches.append("active jobs")
                if len(payload.get("completedJobs", [])) != expected_completed:
                    mismatches.append("completed jobs")
                if len(payload.get("parts", [])) != expected_parts:
                    mismatches.append("parts")
                if len(payload.get("purchaseOrders", [])) != expected_pos:
                    mismatches.append("purchase orders")
                if mismatches:
                    self.integrity_issues.append({"check": "Dashboard / Insights consistency", "severity": "medium", "message": f"Bootstrap payload counts drifted from database counts for: {', '.join(mismatches)}."})

    def summarize_actions(self) -> dict[str, dict]:
        grouped: dict[str, list[ActionResult]] = defaultdict(list)
        for result in self.results:
            grouped[result.action].append(result)
        summary = {}
        for action, results in grouped.items():
            times = [result.elapsed_ms for result in results if result.elapsed_ms > 0]
            failures = [result for result in results if not result.ok]
            summary[action] = {
                "count": len(results),
                "passed": len(failures) == 0,
                "error_rate": round((len(failures) / len(results)) * 100, 2) if results else 0.0,
                "avg_ms": round(statistics.mean(times), 2) if times else 0.0,
                "p95_ms": round(percentile(times, 0.95), 2) if times else 0.0,
                "max_ms": round(max(times), 2) if times else 0.0,
                "target_ms": TARGETS_MS.get(action),
                "sample_errors": [result.error for result in failures[:3] if result.error],
            }
        return summary

    def derive_bottlenecks_and_recommendations(self, action_summary: dict[str, dict]) -> None:
        for action, summary in action_summary.items():
            target_ms = summary.get("target_ms") or 0
            if target_ms and summary["p95_ms"] > target_ms:
                self.bottlenecks.append(f"{action} exceeded target with p95 {summary['p95_ms']}ms against target {target_ms}ms.")
            if summary["error_rate"] > 5:
                self.bottlenecks.append(f"{action} had elevated failures at {summary['error_rate']}%.")
        if any(issue["check"].startswith("Race: Pull") for issue in self.integrity_issues):
            self.recommendations.append("Add transactional stock guards for pulls so two users cannot over-allocate the same inventory at once.")
        if any(issue["check"].startswith("Race: Receive") for issue in self.integrity_issues):
            self.recommendations.append("Protect PO receiving with row-level conflict checks or optimistic locking before increasing quantity_received.")
        if any("silently overwrote" in issue["message"] for issue in self.integrity_issues):
            self.recommendations.append("Add version or updated_at conflict checks on jobs and parts so concurrent edits return a conflict instead of last-write-wins.")
        if action_summary.get("po_create", {}).get("error_rate", 0) > 0:
            self.recommendations.append("Make purchase-order numbering atomic so concurrent PO creation cannot collide on the next PO number.")
        if not self.ai_enabled:
            self.recommendations.append("Configure OPENAI_API_KEY before running the full AI Insights portion so AI response-time and accuracy behavior are measured.")
        if not self.recommendations:
            self.recommendations.append("Current run stayed within the basic harness checks. Next step is to repeat the run on a deployed environment and compare timings against this isolated baseline.")

    def build_report(self) -> dict:
        action_summary = self.summarize_actions()
        self.derive_bottlenecks_and_recommendations(action_summary)
        return {
            "generated_at": datetime.now().isoformat(),
            "scale": self.scale_name,
            "seed": self.seed,
            "workers": self.workers,
            "isolated_database": str(self.test_db_path) if self.test_db_path else "",
            "dataset_summary": self.dataset_summary,
            "performance_targets_ms": TARGETS_MS,
            "scenarios": self.scenario_summaries,
            "actions": action_summary,
            "integrity_issues": self.integrity_issues,
            "bottlenecks": self.bottlenecks,
            "recommendations": self.recommendations,
        }

    def write_report_files(self, report: dict) -> None:
        root = Path(__file__).resolve().parent
        (root / "stress_test_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (root / "stress_test_report.md").write_text(self.render_markdown_report(report), encoding="utf-8")

    def render_markdown_report(self, report: dict) -> str:
        lines = [
            "# Bath Fitters Stress Test Report",
            "",
            f"- Generated: {report['generated_at']}",
            f"- Scale: {report['scale']}",
            f"- Workers: {report['workers']}",
            f"- AI enabled: {'Yes' if self.ai_enabled else 'No'}",
            "",
            "## Seeded Dataset",
            "",
        ]
        for key, value in report["dataset_summary"].items():
            lines.append(f"- {key.replace('_', ' ').title()}: {value}")
        lines.extend(["", "## Scenario Results", "", "| Scenario | Actions | Failures | Avg ms | Passed |", "| --- | ---: | ---: | ---: | --- |"])
        for scenario in report["scenarios"]:
            lines.append(f"| {scenario['name']} | {scenario['total_actions']} | {scenario['failures']} | {scenario['avg_ms']} | {'Yes' if scenario['passed'] else 'No'} |")
        lines.extend(["", "## Action Timings", "", "| Action | Count | Error % | Avg ms | P95 ms | Max ms | Target ms | Passed |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"])
        for action, summary in report["actions"].items():
            lines.append(f"| {action} | {summary['count']} | {summary['error_rate']} | {summary['avg_ms']} | {summary['p95_ms']} | {summary['max_ms']} | {summary['target_ms'] or '-'} | {'Yes' if summary['passed'] else 'No'} |")
        lines.extend(["", "## Integrity Findings", ""])
        if report["integrity_issues"]:
            for issue in report["integrity_issues"]:
                lines.append(f"- [{issue['severity'].upper()}] {issue['check']}: {issue['message']}")
        else:
            lines.append("- No integrity issues were detected in this run.")
        lines.extend(["", "## Bottlenecks", ""])
        if report["bottlenecks"]:
            for item in report["bottlenecks"]:
                lines.append(f"- {item}")
        else:
            lines.append("- No major timing bottlenecks exceeded the configured targets.")
        lines.extend(["", "## Recommendations", ""])
        for recommendation in report["recommendations"]:
            lines.append(f"- {recommendation}")
        return "\n".join(lines) + "\n"


def print_console_summary(report: dict) -> None:
    print("Stress test complete.")
    print(f"Scale: {report['scale']} | Workers: {report['workers']}")
    print("Seeded dataset:")
    for key, value in report["dataset_summary"].items():
        print(f"  - {key}: {value}")
    print("Scenario results:")
    for scenario in report["scenarios"]:
        status = "PASS" if scenario["passed"] else "FAIL"
        print(f"  - {scenario['name']}: {status} | actions={scenario['total_actions']} failures={scenario['failures']} avg_ms={scenario['avg_ms']}")
    print("Action timings:")
    for action, summary in report["actions"].items():
        print(f"  - {action}: count={summary['count']} error_rate={summary['error_rate']}% avg={summary['avg_ms']}ms p95={summary['p95_ms']}ms target={summary['target_ms']}")
    if report["integrity_issues"]:
        print("Integrity issues:")
        for issue in report["integrity_issues"]:
            print(f"  - [{issue['severity']}] {issue['check']}: {issue['message']}")
    else:
        print("Integrity issues: none detected")
    print("Reports written to stress_test_report.json and stress_test_report.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a realistic Bath Fitters stress test harness against an isolated temp database.")
    parser.add_argument("--scale", choices=sorted(SCALE_PRESETS), default="medium", help="Dataset size preset. medium is the default realistic run.")
    parser.add_argument("--workers", type=int, default=None, help="Override concurrent worker count.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for repeatable demo data.")
    parser.add_argument("--keep-db", action="store_true", help="Keep the isolated stress-test database after the run for inspection.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    harness = StressHarness(scale_name=args.scale, seed=args.seed, workers=args.workers, keep_db=args.keep_db)
    report = harness.run()
    print_console_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
