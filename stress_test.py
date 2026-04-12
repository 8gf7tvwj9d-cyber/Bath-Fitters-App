import json
import random
import statistics
import string
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from app import app, get_db

REPORT_PATH = Path("stress_test_report.json")
random.seed(42)


class StressRunner:
    def __init__(self):
        self.results = []
        self.context = {}

    def record(self, name, passed, detail, category, manual=False):
        self.results.append(
            {
                "name": name,
                "passed": bool(passed),
                "detail": detail,
                "category": category,
                "manual": manual,
            }
        )

    def post_json(self, client, url, payload, expected_status=200):
        response = client.post(url, json=payload)
        if response.status_code != expected_status:
            try:
                body = response.get_json()
            except Exception:
                body = response.get_data(as_text=True)
            raise AssertionError(f"{url} returned {response.status_code}, expected {expected_status}: {body}")
        return response

    def bootstrap(self, client, warehouse_id=None):
        suffix = f"?warehouseId={warehouse_id}" if warehouse_id else ""
        started = time.perf_counter()
        response = client.get(f"/api/bootstrap{suffix}")
        elapsed = time.perf_counter() - started
        data = response.get_json()
        return elapsed, data

    def add_part(self, client, warehouse_id, vendor_id, part_number, description, category, stock, reorder_point, unit_cost):
        return self.post_json(
            client,
            "/api/parts",
            {
                "warehouseId": warehouse_id,
                "partNumber": part_number,
                "description": description,
                "category": category,
                "stock": stock,
                "reorderPoint": reorder_point,
                "vendorId": vendor_id,
                "unitCost": unit_cost,
            },
        ).get_json()

    def add_job(self, client, warehouse_id, job_number, title, customer_name, address, technician, scheduled_for, notes, requirements, expected_status=200):
        return self.post_json(
            client,
            "/api/jobs",
            {
                "warehouseId": warehouse_id,
                "jobNumber": job_number,
                "title": title,
                "customerName": customer_name,
                "address": address,
                "technician": technician,
                "scheduledFor": scheduled_for,
                "notes": notes,
                "requirements": requirements,
            },
            expected_status=expected_status,
        )

    def add_purchase_order(self, client, warehouse_id, vendor_id, part_id, quantity, eta, notes):
        return self.post_json(
            client,
            "/api/purchase-orders",
            {
                "warehouseId": warehouse_id,
                "vendorId": vendor_id,
                "partId": part_id,
                "quantity": quantity,
                "eta": eta,
                "notes": notes,
            },
        ).get_json()

    def current_ids(self, data):
        return {
            "part_ids": [part["id"] for part in data["parts"]],
            "job_ids": [job["id"] for job in data["jobs"]],
            "po_ids": [po["id"] for po in data["purchaseOrders"]],
        }

    def summarize(self):
        passed = sum(1 for item in self.results if item["passed"])
        failed = sum(1 for item in self.results if not item["passed"] and not item["manual"])
        manual = sum(1 for item in self.results if item["manual"])
        return {"passed": passed, "failed": failed, "manual": manual, "results": self.results, "context": self.context}


def make_requirements(parts, start_index, count, qty_cycle=(1, 2, 3)):
    requirements = []
    for offset in range(count):
        part = parts[(start_index + offset) % len(parts)]
        requirements.append(
            {
                "partId": part["id"],
                "requiredQuantity": qty_cycle[offset % len(qty_cycle)],
            }
        )
    return requirements


runner = StressRunner()

with app.app_context():
    client = app.test_client()
    runner.post_json(client, "/api/reset", {"warehouseId": 1})

    load_samples = []
    for _ in range(5):
        elapsed, bootstrap = runner.bootstrap(client)
        load_samples.append(elapsed)
    selected_warehouse = bootstrap["selectedWarehouseId"]
    vendors = bootstrap["vendors"]
    vendor_ids = [vendor["id"] for vendor in vendors]
    runner.context["initial_bootstrap_avg_ms"] = round(statistics.mean(load_samples) * 1000, 2)

    data = bootstrap
    base_counts = {
        "parts": len(data["parts"]),
        "jobs": len(data["jobs"]),
        "purchase_orders": len(data["purchaseOrders"]),
    }
    runner.context["base_counts"] = base_counts

    target_parts = 1000
    extra_parts_needed = target_parts - len(data["parts"])
    categories = [
        "Drain Assemblies",
        "Valves",
        "Sealants",
        "Supply Lines",
        "Trim Kits",
        "Faucets",
        "Install Kits",
        "Shower Hardware",
        "Toilet Parts",
        "P-Traps",
    ]
    part_state = data
    for index in range(extra_parts_needed):
        vendor_id = vendor_ids[index % len(vendor_ids)]
        category = categories[index % len(categories)]
        part_state = runner.add_part(
            client,
            selected_warehouse,
            vendor_id,
            f"TST-{index:04d}",
            f"Stress Test {category} Part {index}",
            category,
            stock=(index % 17) + 3,
            reorder_point=(index % 5) + 2,
            unit_cost=round(5 + (index % 23) * 1.13, 2),
        )
    data = part_state
    runner.record(
        "Data Volume - 1000 inventory items",
        len(data["parts"]) >= 1000,
        f"Inventory count after seeding: {len(data['parts'])}",
        "data_volume",
    )

    similar_parts = [
        ("SIM-0001", "White Trim 6in"),
        ("SIM-0002", "White Trim 6 in"),
        ("SIM-0003", "WhiteTrim6"),
    ]
    for number, description in similar_parts:
        data = runner.add_part(client, selected_warehouse, vendor_ids[0], number, description, "Trim Kits", 5, 2, 14.5)
    try:
        runner.add_part(client, selected_warehouse, vendor_ids[0], "SIM-0001", "Duplicate part number", "Trim Kits", 5, 2, 12.0)
        duplicate_blocked = False
    except AssertionError:
        duplicate_blocked = True
    runner.record(
        "Duplicate Part Number Guard",
        duplicate_blocked,
        "Duplicate part numbers are rejected at the API level." if duplicate_blocked else "Duplicate part number was accepted unexpectedly.",
        "duplicate_data",
    )

    negative_response = client.post(
        "/api/parts",
        json={
            "warehouseId": selected_warehouse,
            "partNumber": "NEG-0001",
            "description": "Negative Stock Candidate",
            "category": "Valves",
            "stock": -5,
            "reorderPoint": 1,
            "vendorId": vendor_ids[0],
            "unitCost": 9.99,
        },
    )
    runner.record(
        "Negative Inventory Validation",
        negative_response.status_code == 400,
        f"Negative stock response status: {negative_response.status_code}",
        "inventory_edge_cases",
    )

    low_edge_parts = [
        ("EDGE-0000", 0),
        ("EDGE-0001", 1),
        ("EDGE-0002", 2),
    ]
    for number, stock in low_edge_parts:
        data = runner.add_part(client, selected_warehouse, vendor_ids[0], number, f"Edge Part {stock}", "Valves", stock, 2, 11.0)
    runner.record(
        "Zero and Low Stock Records",
        any(part["part_number"] == "EDGE-0000" for part in data["parts"]) and any(part["stock"] in (0, 1, 2) for part in data["parts"]),
        "Zero and low-stock parts created without crashing.",
        "inventory_edge_cases",
    )

    parts = data["parts"]
    existing_job_count = len(data["jobs"])
    jobs_needed = 200 - existing_job_count
    now = datetime.now()
    last_job_state = data
    one_part_job_index = None
    hundred_part_job_index = None
    for index in range(jobs_needed):
        if index == 0:
            requirement_count = 1
            one_part_job_index = index
        elif index == 1:
            requirement_count = 55
        elif index == 2:
            requirement_count = 100
            hundred_part_job_index = index
        elif index < 8:
            requirement_count = 60
        else:
            requirement_count = 5 + (index % 4)
        requirements = make_requirements(parts, start_index=index * 7, count=requirement_count)
        last_job_state = runner.add_job(
            client,
            selected_warehouse,
            f"STRESS-JOB-{index:03d}",
            f"Stress Job {index % 12}",
            f"Customer {index % 25}",
            f"{100 + index} Test Lane",
            f"Crew {index % 9}",
            (now + timedelta(days=index % 30)).date().isoformat(),
            f"Stress note {index}",
            requirements,
        ).get_json()
    data = last_job_state
    runner.record(
        "Data Volume - 200 jobs",
        len(data["jobs"]) >= 200,
        f"Job count after seeding: {len(data['jobs'])}",
        "data_volume",
    )

    no_parts_job = runner.add_job(
        client,
        selected_warehouse,
        "NO-PARTS-001",
        "No Parts Job",
        "No Parts Customer",
        "1 Empty St",
        "Crew X",
        now.date().isoformat(),
        "Should fail",
        [],
        expected_status=400,
    )
    runner.record(
        "Edge Case Job - No Parts",
        no_parts_job.status_code == 400,
        "API currently blocks jobs with no parts, which is consistent but means this workflow is unsupported.",
        "edge_case_jobs",
    )

    jobs_data = data["jobs"]
    requirements_data = data["jobRequirements"]
    one_part_job = next((job for job in jobs_data if job["job_number"] == "STRESS-JOB-000"), None)
    hundred_part_job = next((job for job in jobs_data if job["job_number"] == "STRESS-JOB-002"), None)
    runner.record(
        "Edge Case Job - One Part",
        one_part_job is not None and sum(1 for req in requirements_data if req["job_id"] == one_part_job["id"]) == 1,
        "Created a single-part job successfully.",
        "edge_case_jobs",
    )
    runner.record(
        "Long List - Job With 100 Parts",
        hundred_part_job is not None and sum(1 for req in requirements_data if req["job_id"] == hundred_part_job["id"]) >= 100,
        "Created a very large job to exercise list rendering and expansion pressure.",
        "long_list",
    )

    existing_po_count = len(data["purchaseOrders"])
    po_needed = 300 - existing_po_count
    last_po_state = data
    for index in range(po_needed):
        part = parts[(index * 3) % len(parts)]
        last_po_state = runner.add_purchase_order(
            client,
            selected_warehouse,
            part["vendor_id"],
            part["id"],
            quantity=5 + (index % 20),
            eta=(now + timedelta(days=(index % 15) + 1)).date().isoformat(),
            notes=f"Stress PO {index}",
        )
    data = last_po_state
    runner.record(
        "Data Volume - 300 purchase orders",
        len(data["purchaseOrders"]) >= 300,
        f"Purchase order count after seeding: {len(data['purchaseOrders'])}",
        "data_volume",
    )

    runner.record(
        "Long List - Purchase Order With 20+ Line Items",
        False,
        "Current data model only supports one part per purchase order, so true multi-line PO stress is not yet supported.",
        "long_list",
    )

    elapsed_heavy = []
    for _ in range(10):
        elapsed, data = runner.bootstrap(client, selected_warehouse)
        elapsed_heavy.append(elapsed)
    avg_ms = statistics.mean(elapsed_heavy) * 1000
    max_ms = max(elapsed_heavy) * 1000
    runner.context["heavy_bootstrap_avg_ms"] = round(avg_ms, 2)
    runner.context["heavy_bootstrap_max_ms"] = round(max_ms, 2)
    runner.record(
        "Data Volume - Bootstrap Load Time",
        avg_ms < 1000,
        f"Average /api/bootstrap under heavy data: {avg_ms:.2f} ms, max {max_ms:.2f} ms",
        "data_volume",
    )

    same_part = parts[0]
    job_a = jobs_data[0]
    job_b = jobs_data[1]
    state_after_add = runner.post_json(client, f"/api/jobs/{job_a['id']}/parts", {
        "warehouseId": selected_warehouse,
        "partId": same_part["id"],
        "requiredQuantity": 4,
    }).get_json()
    state_after_add = runner.post_json(client, f"/api/jobs/{job_b['id']}/parts", {
        "warehouseId": selected_warehouse,
        "partId": same_part["id"],
        "requiredQuantity": 3,
    }).get_json()
    req_a = next(req for req in state_after_add["jobRequirements"] if req["job_id"] == job_a["id"] and req["part_id"] == same_part["id"])
    req_b = next(req for req in state_after_add["jobRequirements"] if req["job_id"] == job_b["id"] and req["part_id"] == same_part["id"])
    before_stock = next(part for part in state_after_add["parts"] if part["id"] == same_part["id"])["stock"]
    state_after_pull = runner.post_json(client, f"/api/job-parts/{req_a['id']}/pull", {
        "warehouseId": selected_warehouse,
        "quantity": 2,
        "notes": "Integrity pull A",
    }).get_json()
    state_after_pull = runner.post_json(client, f"/api/job-parts/{req_b['id']}/pull", {
        "warehouseId": selected_warehouse,
        "quantity": 3,
        "notes": "Integrity pull B",
    }).get_json()
    after_stock = next(part for part in state_after_pull["parts"] if part["id"] == same_part["id"])["stock"]
    runner.record(
        "Data Integrity - Same Part Across Multiple Jobs",
        before_stock - after_stock == 5,
        f"Shared part stock changed from {before_stock} to {after_stock} after pulls across two jobs.",
        "data_integrity",
    )

    over_po = next(po for po in state_after_pull["purchaseOrders"] if po["status"] == "Waiting for Part")
    over_state = runner.post_json(client, f"/api/purchase-orders/{over_po['id']}/receive", {
        "warehouseId": selected_warehouse,
        "quantity": 15,
        "receivedBy": "Stress Test",
        "notes": "Over receiving scenario",
        "verifiedCount": True,
    }).get_json()
    over_po_after = next(po for po in over_state["purchaseOrders"] if po["id"] == over_po["id"])
    runner.record(
        "Over Receiving - Inventory Uses Actual Received Quantity",
        over_po_after["received_quantity"] >= 15,
        f"Received quantity stored as {over_po_after['received_quantity']} on PO {over_po_after['po_number']}.",
        "po_edge_cases",
    )

    partial_part = parts[10]
    partial_state = runner.add_purchase_order(
        client,
        selected_warehouse,
        partial_part["vendor_id"],
        partial_part["id"],
        quantity=50,
        eta=(now + timedelta(days=5)).date().isoformat(),
        notes="Partial receiving scenario",
    )
    partial_po = max(partial_state["purchaseOrders"], key=lambda po: po["id"])
    partial_state = runner.post_json(client, f"/api/purchase-orders/{partial_po['id']}/status", {
        "warehouseId": selected_warehouse,
        "status": "Waiting for Part",
    }).get_json()
    for qty in (20, 15, 30):
        partial_state = runner.post_json(client, f"/api/purchase-orders/{partial_po['id']}/receive", {
            "warehouseId": selected_warehouse,
            "quantity": qty,
            "receivedBy": "Stress Test",
            "notes": f"Partial receipt {qty}",
            "verifiedCount": True,
        }).get_json()
    partial_po_after = next(po for po in partial_state["purchaseOrders"] if po["id"] == partial_po["id"])
    partial_logs = [log for log in partial_state["receivingLogs"] if log["po_id"] == partial_po["id"]]
    runner.record(
        "Partial Receiving - Running Totals",
        partial_po_after["received_quantity"] == 65 and len(partial_logs) == 3,
        f"Received quantity {partial_po_after['received_quantity']} across {len(partial_logs)} receiving entries.",
        "po_edge_cases",
    )

    edit_job = jobs_data[2]
    edit_state = runner.post_json(client, f"/api/jobs/{edit_job['id']}", {
        "warehouseId": selected_warehouse,
        "jobNumber": edit_job['job_number'],
        "title": "Edited Stress Title",
        "customerName": "Edited Customer",
        "address": "999 Edited Ave",
        "technician": "Edited Crew",
        "scheduledFor": now.date().isoformat(),
        "notes": "Edited notes field",
    }).get_json()
    edit_state = runner.post_json(client, f"/api/jobs/{edit_job['id']}/notes", {
        "warehouseId": selected_warehouse,
        "notes": "Short",
    }).get_json()
    long_note = "Special chars !@#$%^&*()[]{}<>?/\\|~ plus long text " + ("x" * 550)
    edit_state = runner.post_json(client, f"/api/jobs/{edit_job['id']}/notes", {
        "warehouseId": selected_warehouse,
        "notes": long_note,
    }).get_json()
    edited_job = next(job for job in edit_state["jobs"] if job["id"] == edit_job["id"])
    runner.record(
        "Job Editing - Persisted Fields",
        edited_job["title"] == "Edited Stress Title" and edited_job["customer_name"] == "Edited Customer" and edited_job["notes"] == long_note,
        "Job details, notes, and long/special-character note persisted correctly.",
        "job_editing",
    )

    rapid_job = jobs_data[3]
    rapid_part = parts[20]
    for index in range(15):
        rapid_state = runner.post_json(client, f"/api/jobs/{rapid_job['id']}/parts", {
            "warehouseId": selected_warehouse,
            "partId": rapid_part['id'],
            "requiredQuantity": 1,
        }).get_json()
        rapid_req = next(req for req in rapid_state["jobRequirements"] if req["job_id"] == rapid_job["id"] and req["part_id"] == rapid_part['id'])
        rapid_state = runner.post_json(client, f"/api/job-parts/{rapid_req['id']}/pull", {
            "warehouseId": selected_warehouse,
            "quantity": 1,
            "notes": "Rapid pull",
        }).get_json()
        rapid_state = runner.post_json(client, f"/api/job-parts/{rapid_req['id']}/return", {
            "warehouseId": selected_warehouse,
            "quantity": 1,
            "notes": "Rapid return",
        }).get_json()
    final_req = next(req for req in rapid_state["jobRequirements"] if req["job_id"] == rapid_job["id"] and req["part_id"] == rapid_part['id'])
    runner.record(
        "Rapid Action - Pull/Return Stability",
        final_req["pulled_quantity"] == 0,
        f"After rapid pull/return cycles, pulled quantity settled at {final_req['pulled_quantity']}.",
        "rapid_actions",
    )

    elapsed_nav = []
    for _ in range(30):
        elapsed, _ = runner.bootstrap(client, selected_warehouse)
        elapsed_nav.append(elapsed)
    runner.record(
        "Navigation/Persistence - Repeated Reloads",
        max(elapsed_nav) < 1.5,
        f"30 repeated bootstrap calls completed. Max response time {max(elapsed_nav) * 1000:.2f} ms.",
        "navigation_persistence",
    )

    persisted_elapsed, persisted_state = runner.bootstrap(client, selected_warehouse)
    persisted_job = next(job for job in persisted_state["jobs"] if job["id"] == edit_job['id'])
    runner.record(
        "Persistence - Data Survives Refresh",
        persisted_job["notes"] == long_note,
        "Edited data remained intact after fresh bootstrap reload.",
        "navigation_persistence",
    )

    runner.record(
        "Long List UI - Layout / Scroll / Dropdown Rendering",
        False,
        "Heavy data for long-list UI was created (100-part jobs, 1000 parts, 300 POs), but actual scrolling, overlap, and dropdown rendering need browser-side verification.",
        "manual_ui",
        manual=True,
    )
    runner.record(
        "Search / Filter Accuracy in Browser",
        False,
        "Similar part names and duplicate-like job names were seeded, but visual search result clarity and rapid filter interaction need browser-side verification.",
        "manual_ui",
        manual=True,
    )
    runner.record(
        "Navigation Stress - Tab Switching / State Persistence in Browser",
        False,
        "Repeated bootstrap reloads passed, but actual rapid tab switching and dropdown persistence need browser-side verification.",
        "manual_ui",
        manual=True,
    )
    runner.record(
        "Full System UI Stress - Smooth Scrolling / Freeze Check",
        False,
        "The backend and payload stress run completed under heavy data. Browser responsiveness still needs manual validation on the live UI.",
        "manual_ui",
        manual=True,
    )

    with app.app_context():
        db = get_db()
        counts = {
            "parts": db.execute("SELECT COUNT(*) AS count FROM parts WHERE warehouse_id = ?", (selected_warehouse,)).fetchone()["count"],
            "jobs": db.execute("SELECT COUNT(*) AS count FROM jobs WHERE warehouse_id = ?", (selected_warehouse,)).fetchone()["count"],
            "purchase_orders": db.execute("SELECT COUNT(*) AS count FROM purchase_orders WHERE warehouse_id = ?", (selected_warehouse,)).fetchone()["count"],
            "job_requirements": db.execute("SELECT COUNT(*) AS count FROM job_part_requirements JOIN jobs ON jobs.id = job_part_requirements.job_id WHERE jobs.warehouse_id = ?", (selected_warehouse,)).fetchone()["count"],
            "receiving_logs": db.execute("SELECT COUNT(*) AS count FROM receiving_logs JOIN purchase_orders ON purchase_orders.id = receiving_logs.po_id WHERE purchase_orders.warehouse_id = ?", (selected_warehouse,)).fetchone()["count"],
        }
    runner.context["final_counts"] = counts

summary = runner.summarize()
REPORT_PATH.write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
