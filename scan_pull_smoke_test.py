from __future__ import annotations

import json
from pathlib import Path

from app import app, get_db, init_db


REPORT_PATH = Path("scan_pull_smoke_test_report.json")


class SmokeFailure(Exception):
    pass


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def post_json(client, url: str, payload: dict, expected_status: int = 200) -> dict:
    response = client.post(url, json=payload)
    body = response.get_json(silent=True)
    if response.status_code != expected_status:
        raise SmokeFailure(f"{url} returned {response.status_code}, expected {expected_status}: {body}")
    return body or {}


def seed_context() -> dict:
    init_db()
    with app.app_context():
        db = get_db()
        warehouse_id = int(db.execute("SELECT id FROM warehouses ORDER BY id LIMIT 1").fetchone()["id"])
        job = db.execute(
            "SELECT * FROM jobs WHERE warehouse_id = ? AND status != 'Completed' ORDER BY id LIMIT 1",
            (warehouse_id,),
        ).fetchone()
        expect(job is not None, "No active demo job found.")

        assigned_requirement = db.execute(
            """
            SELECT * FROM job_part_requirements
            WHERE job_id = ? AND pulled_quantity < required_quantity
            ORDER BY id
            LIMIT 1
            """,
            (int(job["id"]),),
        ).fetchone()
        expect(assigned_requirement is not None, "No assigned job part with remaining quantity found.")

        assigned_part = db.execute(
            "SELECT * FROM parts WHERE id = ?",
            (int(assigned_requirement["part_id"]),),
        ).fetchone()
        expect(assigned_part is not None, "Assigned part row missing.")

        unassigned_part = db.execute(
            """
            SELECT * FROM parts
            WHERE warehouse_id = ?
              AND id NOT IN (SELECT part_id FROM job_part_requirements WHERE job_id = ?)
            ORDER BY id
            LIMIT 1
            """,
            (warehouse_id, int(job["id"])),
        ).fetchone()
        expect(unassigned_part is not None, "No unassigned part found for miscellaneous usage test.")

        return {
            "warehouse_id": warehouse_id,
            "job_id": int(job["id"]),
            "job_number": job["job_number"],
            "assigned_part_id": int(assigned_part["id"]),
            "assigned_scan_code": assigned_part["scan_code"],
            "assigned_part_number": assigned_part["part_number"],
            "remaining_quantity": int(assigned_requirement["required_quantity"]) - int(assigned_requirement["pulled_quantity"]),
            "unassigned_part_id": int(unassigned_part["id"]),
            "unassigned_scan_code": unassigned_part["scan_code"],
            "unassigned_part_number": unassigned_part["part_number"],
        }


def run() -> dict:
    context = seed_context()
    client = app.test_client()
    results: list[dict] = []

    def record(name: str, passed: bool, detail: str) -> None:
        results.append({"name": name, "passed": passed, "detail": detail})

    try:
        matched = post_json(
            client,
            f"/api/jobs/{context['job_id']}/scan-match",
            {"warehouseId": context["warehouse_id"], "scanValue": context["assigned_scan_code"]},
        )
        expect(matched["part"]["assignedToJob"] is True, "Assigned scan did not map to a job part.")
        record("assigned scan match", True, matched["part"]["partNumber"])

        pulled = post_json(
            client,
            f"/api/jobs/{context['job_id']}/scan-pull",
            {
                "warehouseId": context["warehouse_id"],
                "partId": context["assigned_part_id"],
                "scanValue": context["assigned_scan_code"],
                "quantity": 1,
                "action": "job_requirement",
            },
        )
        expect(pulled["scanLogEntry"]["action"] == "Pulled for job", "Assigned scan pull did not complete normally.")
        record("assigned scan pull", True, pulled["scanLogEntry"]["partNumber"])

        overpull_response = client.post(
            f"/api/jobs/{context['job_id']}/scan-pull",
            json={
                "warehouseId": context["warehouse_id"],
                "partId": context["assigned_part_id"],
                "scanValue": context["assigned_scan_code"],
                "quantity": 999,
                "action": "job_requirement",
            },
        )
        expect(overpull_response.status_code == 400, "Over-pull should be blocked without confirmation.")
        record("over-pull safeguard", True, "Blocked without confirmation")

        unmatched = post_json(
            client,
            f"/api/jobs/{context['job_id']}/scan-match",
            {"warehouseId": context["warehouse_id"], "scanValue": context["unassigned_scan_code"]},
        )
        expect(unmatched["part"]["assignedToJob"] is False, "Unassigned scan unexpectedly matched a job requirement.")
        record("unassigned scan warning path", True, unmatched["part"]["partNumber"])

        misc = post_json(
            client,
            f"/api/jobs/{context['job_id']}/scan-pull",
            {
                "warehouseId": context["warehouse_id"],
                "partId": context["unassigned_part_id"],
                "scanValue": context["unassigned_scan_code"],
                "quantity": 1,
                "action": "misc_usage",
            },
        )
        expect(misc["scanLogEntry"]["action"] == "Marked as miscellaneous usage", "Miscellaneous scan pull did not complete.")
        record("miscellaneous usage pull", True, misc["scanLogEntry"]["partNumber"])
    except SmokeFailure as error:
        record("smoke test", False, str(error))

    report = {"context": context, "results": results, "passed": all(item["passed"] for item in results)}
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    outcome = run()
    print(json.dumps(outcome, indent=2))
    raise SystemExit(0 if outcome["passed"] else 1)
