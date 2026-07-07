from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
import sqlite3
import smtplib
from contextlib import closing
from datetime import datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from io import BytesIO
from pathlib import Path
from urllib import error as urllib_error, request as urllib_request
from uuid import uuid4

from flask import Flask, g, jsonify, render_template, request, send_file, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = Path("/tmp/shopflow") if os.environ.get("VERCEL") else BASE_DIR / "instance"
DATA_DIR = Path(os.environ.get("SHOPFLOW_DATA_DIR", DEFAULT_DATA_DIR))
DB_PATH = Path(os.environ.get("SHOPFLOW_DB_PATH", DATA_DIR / "shopflow.db"))
ATTACHMENTS_DIR = Path(os.environ.get("SHOPFLOW_ATTACHMENTS_DIR", DATA_DIR / "job_attachments"))
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".txt",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
}

app = Flask(__name__, template_folder="templates", static_folder="assets", static_url_path="/assets")
app.secret_key = os.environ.get("SHOPFLOW_SECRET_KEY", "shopflow-dev-secret")
app.logger.setLevel(logging.INFO)

ROLE_MANAGER = "manager"
ROLE_ADMIN = "admin"
ROLE_WAREHOUSE_MANAGER = "warehouse_manager"
ROLE_INSTALLER = "installer"
ROLE_SERVICE_TECH = "service_tech"
ROLE_VIEWER = "viewer"
WORKER_ROLES = {ROLE_INSTALLER, ROLE_SERVICE_TECH}
JOB_TYPE_OPTIONS = ("Install", "Service", "Warranty", "Detail")
JOB_STATUS_OPTIONS = (
    "New",
    "Scheduled",
    "In Progress",
    "Waiting on Parts",
    "Return Trip Needed",
    "Ready to Go",
    "Active",
    "Completed",
    "Closed",
    "Cancelled",
)
SERVICE_CODE_OPTIONS = ("Service", "Warranty", "Callback", "Evaluation", "Parts Follow-Up", "Other")
SERVICE_PROBABLE_ISSUE_OPTIONS = (
    "Valve / Cartridge",
    "Diverter",
    "Handle Hard To Turn",
    "Caulking",
    "Plumbing Leak",
    "Drain Issue",
    "Cosmetic",
    "Measurement / Final Check",
    "Missing / Wrong Parts",
    "Product Defect",
    "Customer Concern",
    "Other",
)
SERVICE_CATEGORY_OPTIONS = SERVICE_PROBABLE_ISSUE_OPTIONS
SERVICE_URGENCY_OPTIONS = ("Low", "Normal", "High", "Urgent")
PAYMENT_METHOD_OPTIONS = ("No Payment Due", "Cash", "Credit Card", "Check")
SERVICE_FAULT_CATEGORY_OPTIONS = ("Customer", "Installer", "Product", "Evaluation", "Additional Items")
YES_NO_OPTIONS = ("Unknown", "Yes", "No")
DETAIL_DISCREPANCY_CATEGORIES = (
    "Measurement mismatch",
    "Product mismatch",
    "Accessory mismatch",
    "Plumbing / valve mismatch",
    "Color / finish mismatch",
    "Site condition issue",
    "Customer expectation mismatch",
    "Missing paperwork info",
    "Other",
)
PERMISSION_KEYS = (
    "inventory_access",
    "job_access",
    "purchase_orders_access",
    "receiving_access",
    "notes_access",
    "user_management",
    "reporting_access",
    "receive_jobs",
    "complete_jobs",
    "edit_records",
    "delete_records",
)
DEFAULT_ROLE_PERMISSIONS = {
    ROLE_ADMIN: {key: 1 for key in PERMISSION_KEYS},
    ROLE_MANAGER: {
        "inventory_access": 1,
        "job_access": 1,
        "purchase_orders_access": 1,
        "receiving_access": 1,
        "notes_access": 1,
        "user_management": 1,
        "reporting_access": 1,
        "receive_jobs": 1,
        "complete_jobs": 1,
        "edit_records": 1,
        "delete_records": 1,
    },
    ROLE_WAREHOUSE_MANAGER: {
        "inventory_access": 1,
        "job_access": 1,
        "purchase_orders_access": 1,
        "receiving_access": 1,
        "notes_access": 1,
        "user_management": 0,
        "reporting_access": 1,
        "receive_jobs": 1,
        "complete_jobs": 1,
        "edit_records": 1,
        "delete_records": 0,
    },
    ROLE_INSTALLER: {
        "inventory_access": 0,
        "job_access": 1,
        "purchase_orders_access": 0,
        "receiving_access": 0,
        "notes_access": 1,
        "user_management": 0,
        "reporting_access": 0,
        "receive_jobs": 0,
        "complete_jobs": 1,
        "edit_records": 0,
        "delete_records": 0,
    },
    ROLE_SERVICE_TECH: {
        "inventory_access": 0,
        "job_access": 1,
        "purchase_orders_access": 0,
        "receiving_access": 0,
        "notes_access": 1,
        "user_management": 0,
        "reporting_access": 0,
        "receive_jobs": 0,
        "complete_jobs": 1,
        "edit_records": 0,
        "delete_records": 0,
    },
    ROLE_VIEWER: {
        "inventory_access": 0,
        "job_access": 1,
        "purchase_orders_access": 0,
        "receiving_access": 0,
        "notes_access": 0,
        "user_management": 0,
        "reporting_access": 1,
        "receive_jobs": 0,
        "complete_jobs": 0,
        "edit_records": 0,
        "delete_records": 0,
    },
}
GLOBAL_JOB_ACCESS_ROLES = {ROLE_ADMIN, ROLE_MANAGER, ROLE_WAREHOUSE_MANAGER, ROLE_VIEWER}
FEATURE_FLAGS = {
    "inventory": os.environ.get("SHOPFLOW_FEATURE_INVENTORY", "1") != "0",
    "jobs": os.environ.get("SHOPFLOW_FEATURE_JOBS", "1") != "0",
    "purchase_orders": os.environ.get("SHOPFLOW_FEATURE_PURCHASE_ORDERS", "1") != "0",
    "receiving": os.environ.get("SHOPFLOW_FEATURE_RECEIVING", "1") != "0",
    "insights": os.environ.get("SHOPFLOW_FEATURE_INSIGHTS", "1") != "0",
    "users": os.environ.get("SHOPFLOW_FEATURE_USERS", "1") != "0",
}


def canonical_job_type(job_type: str | None, title: str | None = None) -> str:
    raw = str(job_type or "").strip()
    if raw in JOB_TYPE_OPTIONS:
        return raw
    haystack = f"{raw} {str(title or '').strip()}".lower()
    if any(keyword in haystack for keyword in ("detail", "measure", "measurement", "verify", "verification")):
        return "Detail"
    if "warranty" in haystack:
        return "Warranty"
    if any(keyword in haystack for keyword in ("service", "repair", "follow-up", "follow up", "callback")):
        return "Service"
    return "Install"


def is_service_job_type(job_type: str | None) -> bool:
    return canonical_job_type(job_type) in {"Service", "Warranty"}


def is_detail_job_type(job_type: str | None) -> bool:
    return canonical_job_type(job_type) == "Detail"


def allowed_job_types_for_role(role: str | None) -> set[str]:
    normalized = str(role or "").strip()
    if normalized == ROLE_INSTALLER:
        return {"Install", "Detail"}
    if normalized == ROLE_SERVICE_TECH:
        return {"Service", "Warranty"}
    return set(JOB_TYPE_OPTIONS)


def normalize_choice(value: object, allowed: tuple[str, ...], default: str = "") -> str:
    text = str(value or "").strip()
    return text if text in allowed else default


def normalize_service_job_payload(payload: dict, existing: dict | sqlite3.Row | None = None) -> dict[str, object]:
    existing_data = dict(existing or {})

    def text(key: str, fallback: str = "") -> str:
        value = payload.get(key)
        if value is None:
            return str(existing_data.get(key, fallback) or fallback).strip()
        return str(value or "").strip()

    def integer(key: str) -> int:
        value = payload.get(key, existing_data.get(key, 0))
        try:
            return max(int(value or 0), 0)
        except (TypeError, ValueError):
            return 0

    def decimal_text(key: str) -> str:
        value = payload.get(key)
        if value is None:
            return str(existing_data.get(key, "") or "").strip()
        text_value = str(value or "").strip()
        if not text_value:
            return ""
        try:
            return f"{float(text_value):.2f}"
        except ValueError:
            return ""

    normalized = {
        "service_code": normalize_choice(text("service_code"), SERVICE_CODE_OPTIONS, "Service"),
        "service_status": normalize_choice(text("service_status", "Scheduled"), JOB_STATUS_OPTIONS, "Scheduled"),
        "office_number": text("office_number"),
        "zone_number": text("zone_number"),
        "contract_number": text("contract_number"),
        "call_date": text("call_date"),
        "scheduled_time": text("scheduled_time"),
        "estimated_hours": text("estimated_hours"),
        "prior_visit_count": integer("prior_visit_count"),
        "customer_name_primary": text("customer_name_primary", text("customerName")),
        "customer_name_secondary": text("customer_name_secondary"),
        "address_line_1": text("address_line_1", text("address")),
        "city": text("city"),
        "state": text("state"),
        "zip": text("zip"),
        "primary_phone": text("primary_phone"),
        "secondary_phone": text("secondary_phone"),
        "email": text("email"),
        "best_contact_note": text("best_contact_note"),
        "sale_date": text("sale_date"),
        "salesperson": text("salesperson"),
        "install_date": text("install_date"),
        "product_type": text("product_type"),
        "color": text("color"),
        "customer_complaint": text("customer_complaint"),
        "dispatch_description": text("dispatch_description"),
        "probable_issue_category": normalize_choice(
            text("probable_issue_category"), SERVICE_PROBABLE_ISSUE_OPTIONS, "Other"
        ),
        "service_category": normalize_choice(text("service_category"), SERVICE_CATEGORY_OPTIONS, "Other"),
        "urgency": normalize_choice(text("urgency"), SERVICE_URGENCY_OPTIONS, "Normal"),
        "internal_notes": text("internal_notes"),
        "return_trip_required": normalize_choice(text("return_trip_required"), YES_NO_OPTIONS, "Unknown"),
        "return_reason": text("return_reason"),
        "return_estimated_hours": text("return_estimated_hours"),
        "survey_left": normalize_choice(text("survey_left"), YES_NO_OPTIONS, "Unknown"),
        "parts_to_order": text("parts_to_order"),
        "service_cost": decimal_text("service_cost"),
        "payment_method": normalize_choice(text("payment_method"), PAYMENT_METHOD_OPTIONS, "No Payment Due"),
        "no_payment_due": normalize_choice(text("no_payment_due"), YES_NO_OPTIONS, "Unknown"),
        "start_time": text("start_time"),
        "end_time": text("end_time"),
        "travel_time_minutes": integer("travel_time_minutes"),
        "total_time_minutes": integer("total_time_minutes"),
        "customer_comments": text("customer_comments"),
        "customer_signature": text("customer_signature"),
        "paid_service": normalize_choice(text("paid_service"), YES_NO_OPTIONS, "Unknown"),
        "service_fault_category": normalize_choice(
            text("service_fault_category"), SERVICE_FAULT_CATEGORY_OPTIONS, "Evaluation"
        ),
        "service_item": text("service_item"),
        "service_issue": text("service_issue"),
        "manager_approval_name": text("manager_approval_name"),
        "manager_approval_date": text("manager_approval_date"),
        "return_for_credit": normalize_choice(text("return_for_credit"), YES_NO_OPTIONS, "Unknown"),
        "service_record_id": text("service_record_id"),
    }
    return normalized


def validate_service_job_fields(service_fields: dict[str, object]) -> str | None:
    if str(service_fields.get("return_trip_required") or "") == "Yes" and not str(
        service_fields.get("return_reason") or ""
    ).strip():
        return "Add a return reason when marking this service ticket for a return trip."
    return None


def normalize_detail_job_payload(payload: dict, existing: dict | sqlite3.Row | None = None) -> dict[str, object]:
    existing_data = dict(existing or {})

    def text(key: str, fallback: str = "") -> str:
        value = payload.get(key)
        if value is None:
            return str(existing_data.get(key, fallback) or fallback).strip()
        return str(value or "").strip()

    return {
        "linked_contract_number": text("linked_contract_number", text("contract_number")),
        "linked_sale_record_id": text("linked_sale_record_id"),
        "extracted_document_summary": text("extracted_document_summary"),
        "extracted_product_type": text("extracted_product_type"),
        "extracted_color": text("extracted_color"),
        "extracted_configuration": text("extracted_configuration"),
        "extracted_measurements": text("extracted_measurements"),
        "extracted_accessories": text("extracted_accessories"),
        "extracted_notes": text("extracted_notes"),
        "extracted_special_requirements": text("extracted_special_requirements"),
        "extracted_confidence_flags": text("extracted_confidence_flags"),
        "detail_checklist": text("detail_checklist"),
        "confirmed_measurements": text("confirmed_measurements"),
        "confirmed_layout": normalize_choice(text("confirmed_layout"), YES_NO_OPTIONS, "Unknown"),
        "confirmed_product_match": normalize_choice(text("confirmed_product_match"), YES_NO_OPTIONS, "Unknown"),
        "confirmed_accessories": normalize_choice(text("confirmed_accessories"), YES_NO_OPTIONS, "Unknown"),
        "confirmed_customer_expectations": normalize_choice(
            text("confirmed_customer_expectations"), YES_NO_OPTIONS, "Unknown"
        ),
        "discrepancies_found": normalize_choice(text("discrepancies_found"), YES_NO_OPTIONS, "Unknown"),
        "discrepancy_category": normalize_choice(text("discrepancy_category"), DETAIL_DISCREPANCY_CATEGORIES, "Other"),
        "discrepancy_notes": text("discrepancy_notes"),
        "changes_needed": normalize_choice(text("changes_needed"), YES_NO_OPTIONS, "Unknown"),
        "ready_for_install": normalize_choice(text("ready_for_install"), YES_NO_OPTIONS, "Unknown"),
        "follow_up_required": normalize_choice(text("follow_up_required"), YES_NO_OPTIONS, "Unknown"),
        "install_handoff_summary": text("install_handoff_summary"),
    }


def default_detail_checklist(detail_fields: dict[str, object]) -> str:
    checklist = [
        "Confirm final wall-to-wall and height measurements.",
        "Confirm drain location and any offset concerns.",
        "Confirm valve/plumbing wall and access conditions.",
        "Confirm sold configuration matches actual site conditions.",
        "Confirm product type and color/finish with customer.",
        "Confirm accessories, options, shelves, seats, bars, doors, and glass selection.",
        "Confirm customer expectations and any exclusions from the sold paperwork.",
        "Confirm no access, parking, demolition, or installation obstacles.",
    ]
    if str(detail_fields.get("extracted_accessories") or "").strip():
        checklist.append(f"Review listed accessories: {detail_fields['extracted_accessories']}.")
    if str(detail_fields.get("extracted_special_requirements") or "").strip():
        checklist.append(f"Review special requirements: {detail_fields['extracted_special_requirements']}.")
    return "\n".join(f"- {item}" for item in checklist)


def detail_handoff_summary(detail_fields: dict[str, object]) -> str:
    lines = [
        f"Measurements: {detail_fields.get('confirmed_measurements') or detail_fields.get('extracted_measurements') or 'Not confirmed'}",
        f"Configuration: {detail_fields.get('extracted_configuration') or 'Not listed'}",
        f"Product / color: {detail_fields.get('extracted_product_type') or 'Not listed'} / {detail_fields.get('extracted_color') or 'Not listed'}",
        f"Accessories: {detail_fields.get('extracted_accessories') or 'Not listed'}",
        f"Discrepancies: {detail_fields.get('discrepancies_found') or 'Unknown'} - {detail_fields.get('discrepancy_notes') or 'No notes'}",
        f"Changes needed: {detail_fields.get('changes_needed') or 'Unknown'}",
        f"Ready for install: {detail_fields.get('ready_for_install') or 'Unknown'}",
    ]
    return "\n".join(lines)


def apply_detail_job_fields(db: sqlite3.Connection, job_id: int, detail_fields: dict[str, object], actor_id: int | None) -> None:
    if not str(detail_fields.get("detail_checklist") or "").strip():
        detail_fields["detail_checklist"] = default_detail_checklist(detail_fields)
    if str(detail_fields.get("ready_for_install") or "") == "Yes":
        detail_fields["install_handoff_summary"] = detail_handoff_summary(detail_fields)
    db.execute(
        """
        UPDATE jobs
        SET linked_contract_number = ?, linked_sale_record_id = ?, extracted_document_summary = ?,
            extracted_product_type = ?, extracted_color = ?, extracted_configuration = ?, extracted_measurements = ?,
            extracted_accessories = ?, extracted_notes = ?, extracted_special_requirements = ?, extracted_confidence_flags = ?,
            detail_checklist = ?, confirmed_measurements = ?, confirmed_layout = ?, confirmed_product_match = ?,
            confirmed_accessories = ?, confirmed_customer_expectations = ?, discrepancies_found = ?, discrepancy_category = ?,
            discrepancy_notes = ?, changes_needed = ?, ready_for_install = ?, follow_up_required = ?,
            install_handoff_summary = ?, updated_by_user_id = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            detail_fields["linked_contract_number"],
            detail_fields["linked_sale_record_id"],
            detail_fields["extracted_document_summary"],
            detail_fields["extracted_product_type"],
            detail_fields["extracted_color"],
            detail_fields["extracted_configuration"],
            detail_fields["extracted_measurements"],
            detail_fields["extracted_accessories"],
            detail_fields["extracted_notes"],
            detail_fields["extracted_special_requirements"],
            detail_fields["extracted_confidence_flags"],
            detail_fields["detail_checklist"],
            detail_fields["confirmed_measurements"],
            detail_fields["confirmed_layout"],
            detail_fields["confirmed_product_match"],
            detail_fields["confirmed_accessories"],
            detail_fields["confirmed_customer_expectations"],
            detail_fields["discrepancies_found"],
            detail_fields["discrepancy_category"],
            detail_fields["discrepancy_notes"],
            detail_fields["changes_needed"],
            detail_fields["ready_for_install"],
            detail_fields["follow_up_required"],
            detail_fields["install_handoff_summary"],
            actor_id,
            datetime.now().isoformat(),
            job_id,
        ),
    )


def extract_text_from_attachment(path: Path, original_name: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    suffix = Path(original_name).suffix.lower()
    try:
        data = path.read_bytes()
    except OSError:
        return "", ["Unable to read uploaded file for extraction."]
    if suffix in {".txt", ".csv", ".tsv", ".md"}:
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                return data.decode(encoding, errors="ignore"), flags
            except UnicodeError:
                continue
    if suffix == ".pdf":
        flags.append("PDF extraction is basic in this version. Review original document for accuracy.")
        text = data.decode("latin-1", errors="ignore")
        cleaned = re.sub(r"[^A-Za-z0-9@#.,:/\-\s]", " ", text)
        return re.sub(r"\s+", " ", cleaned), flags
    flags.append(f"{suffix or 'This'} file type has limited text extraction support.")
    return data.decode("latin-1", errors="ignore"), flags


def regex_value(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip(" :;-")
    return ""


def derive_detail_extraction(existing: sqlite3.Row, text: str, flags: list[str]) -> dict[str, object]:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) > 1200:
        compact = compact[:1200].rsplit(" ", 1)[0] + "..."
    extracted = normalize_detail_job_payload({}, existing)
    extracted.update(
        {
            "extracted_document_summary": compact or "No readable text was extracted. Review the original document.",
            "extracted_product_type": regex_value(compact, [r"product(?: type)?[:#\s-]+([^.,;\n]{2,80})"]),
            "extracted_color": regex_value(compact, [r"(?:color|finish)[:#\s-]+([^.,;\n]{2,80})"]),
            "extracted_configuration": regex_value(
                compact, [r"(?:configuration|wall configuration|layout)[:#\s-]+([^.;\n]{2,140})"]
            ),
            "extracted_measurements": regex_value(
                compact, [r"(?:measurements?|dimensions?|size)[:#\s-]+([^.;\n]{2,160})"]
            ),
            "extracted_accessories": regex_value(
                compact, [r"(?:accessories|options|add-ons|addons)[:#\s-]+([^.;\n]{2,180})"]
            ),
            "extracted_notes": regex_value(compact, [r"(?:notes?|important notes?)[:#\s-]+([^.;\n]{2,220})"]),
            "extracted_special_requirements": regex_value(
                compact, [r"(?:special instructions?|special requirements?|constraints?)[:#\s-]+([^.;\n]{2,220})"]
            ),
            "extracted_confidence_flags": "\n".join(flags) if flags else "Review extracted details against the source document before confirming.",
        }
    )
    extracted["detail_checklist"] = default_detail_checklist(extracted)
    return extracted


def normalize_scan_code(value: object) -> str:
    return str(value or "").strip().upper()


def smtp_settings() -> dict[str, object]:
    host = os.environ.get("SHOPFLOW_SMTP_HOST", "").strip()
    port = int(os.environ.get("SHOPFLOW_SMTP_PORT", "587") or 587)
    username = os.environ.get("SHOPFLOW_SMTP_USERNAME", "").strip()
    password = os.environ.get("SHOPFLOW_SMTP_PASSWORD", "")
    from_email = os.environ.get("SHOPFLOW_FROM_EMAIL", username).strip()
    from_name = os.environ.get("SHOPFLOW_FROM_NAME", "Bath Fitters WMS").strip()
    use_tls = os.environ.get("SHOPFLOW_SMTP_USE_TLS", "1").strip().lower() not in {"0", "false", "no"}
    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "from_email": from_email,
        "from_name": from_name,
        "use_tls": use_tls,
        "enabled": bool(host and from_email),
    }


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


@app.before_request
def require_api_authentication():
    if not request.path.startswith("/api/"):
        return None
    if request.path in {"/api/auth/login", "/api/auth/session", "/api/auth/logout"}:
        return None
    if current_user_record() is None:
        return auth_error("Sign in required.", 401)
    return None


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
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
            ensure_app_counters(db)
            ensure_default_users(db)
            ensure_default_role_permissions(db)
            sync_job_assigned_users(db)
            db.commit()
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
        DROP TABLE IF EXISTS job_attachments;
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

        CREATE TABLE IF NOT EXISTS order_form_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            form_variant TEXT NOT NULL DEFAULT 'bathbuild',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            lead_time_days INTEGER NOT NULL,
            linked_template_id TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS role_permissions (
            role TEXT PRIMARY KEY,
            inventory_access INTEGER NOT NULL DEFAULT 0,
            job_access INTEGER NOT NULL DEFAULT 0,
            purchase_orders_access INTEGER NOT NULL DEFAULT 0,
            receiving_access INTEGER NOT NULL DEFAULT 0,
            notes_access INTEGER NOT NULL DEFAULT 0,
            user_management INTEGER NOT NULL DEFAULT 0,
            reporting_access INTEGER NOT NULL DEFAULT 0,
            receive_jobs INTEGER NOT NULL DEFAULT 0,
            complete_jobs INTEGER NOT NULL DEFAULT 0,
            edit_records INTEGER NOT NULL DEFAULT 0,
            delete_records INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER NOT NULL,
            part_number TEXT NOT NULL,
            scan_code TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            item_type TEXT NOT NULL DEFAULT 'stocked',
            stock INTEGER NOT NULL,
            reorder_point INTEGER NOT NULL,
            vendor_id INTEGER NOT NULL,
            unit_cost REAL NOT NULL,
            created_by_user_id INTEGER,
            updated_by_user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (vendor_id) REFERENCES vendors(id),
            FOREIGN KEY (created_by_user_id) REFERENCES users(id),
            FOREIGN KEY (updated_by_user_id) REFERENCES users(id),
            UNIQUE (warehouse_id, part_number)
        );

        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER NOT NULL,
            po_number TEXT NOT NULL UNIQUE,
            vendor_id INTEGER NOT NULL,
            template_id TEXT NOT NULL DEFAULT '',
            eta TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT '',
            created_by_user_id INTEGER,
            updated_by_user_id INTEGER,
            part_id INTEGER,
            quantity INTEGER NOT NULL DEFAULT 0,
            received_quantity INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (vendor_id) REFERENCES vendors(id),
            FOREIGN KEY (part_id) REFERENCES parts(id),
            FOREIGN KEY (created_by_user_id) REFERENCES users(id),
            FOREIGN KEY (updated_by_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS purchase_order_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_order_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            quantity_ordered INTEGER NOT NULL,
            quantity_received INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
            FOREIGN KEY (part_id) REFERENCES parts(id)
        );

        CREATE TABLE IF NOT EXISTS order_list_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            vendor_id INTEGER NOT NULL,
            template_id TEXT NOT NULL DEFAULT '',
            quantity_requested INTEGER NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT '',
            created_by_user_id INTEGER,
            updated_by_user_id INTEGER,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (part_id) REFERENCES parts(id),
            FOREIGN KEY (vendor_id) REFERENCES vendors(id),
            FOREIGN KEY (created_by_user_id) REFERENCES users(id),
            FOREIGN KEY (updated_by_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS receiving_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            received_by TEXT NOT NULL,
            notes TEXT NOT NULL,
            created_at TEXT NOT NULL,
            checked_in_by_user_id INTEGER,
            checked_in_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (po_id) REFERENCES purchase_orders(id),
            FOREIGN KEY (part_id) REFERENCES parts(id),
            FOREIGN KEY (checked_in_by_user_id) REFERENCES users(id)
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
            created_by_user_id INTEGER,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (part_id) REFERENCES parts(id),
            FOREIGN KEY (created_by_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER NOT NULL,
            job_number TEXT NOT NULL,
            title TEXT NOT NULL,
            customer_name TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            scheduled_for TEXT NOT NULL DEFAULT '',
            job_type TEXT NOT NULL DEFAULT '',
            technician TEXT NOT NULL,
            assigned_user_id INTEGER,
            status TEXT NOT NULL,
            notes TEXT NOT NULL,
            service_code TEXT NOT NULL DEFAULT '',
            office_number TEXT NOT NULL DEFAULT '',
            zone_number TEXT NOT NULL DEFAULT '',
            contract_number TEXT NOT NULL DEFAULT '',
            call_date TEXT NOT NULL DEFAULT '',
            scheduled_time TEXT NOT NULL DEFAULT '',
            estimated_hours TEXT NOT NULL DEFAULT '',
            prior_visit_count INTEGER NOT NULL DEFAULT 0,
            customer_name_primary TEXT NOT NULL DEFAULT '',
            customer_name_secondary TEXT NOT NULL DEFAULT '',
            address_line_1 TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '',
            state TEXT NOT NULL DEFAULT '',
            zip TEXT NOT NULL DEFAULT '',
            primary_phone TEXT NOT NULL DEFAULT '',
            secondary_phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            best_contact_note TEXT NOT NULL DEFAULT '',
            sale_date TEXT NOT NULL DEFAULT '',
            salesperson TEXT NOT NULL DEFAULT '',
            install_date TEXT NOT NULL DEFAULT '',
            product_type TEXT NOT NULL DEFAULT '',
            color TEXT NOT NULL DEFAULT '',
            customer_complaint TEXT NOT NULL DEFAULT '',
            dispatch_description TEXT NOT NULL DEFAULT '',
            probable_issue_category TEXT NOT NULL DEFAULT '',
            service_category TEXT NOT NULL DEFAULT '',
            urgency TEXT NOT NULL DEFAULT '',
            internal_notes TEXT NOT NULL DEFAULT '',
            return_trip_required TEXT NOT NULL DEFAULT '',
            return_reason TEXT NOT NULL DEFAULT '',
            return_estimated_hours TEXT NOT NULL DEFAULT '',
            survey_left TEXT NOT NULL DEFAULT '',
            parts_to_order TEXT NOT NULL DEFAULT '',
            service_cost TEXT NOT NULL DEFAULT '',
            payment_method TEXT NOT NULL DEFAULT '',
            no_payment_due TEXT NOT NULL DEFAULT '',
            start_time TEXT NOT NULL DEFAULT '',
            end_time TEXT NOT NULL DEFAULT '',
            travel_time_minutes INTEGER NOT NULL DEFAULT 0,
            total_time_minutes INTEGER NOT NULL DEFAULT 0,
            customer_comments TEXT NOT NULL DEFAULT '',
            customer_signature TEXT NOT NULL DEFAULT '',
            paid_service TEXT NOT NULL DEFAULT '',
            service_fault_category TEXT NOT NULL DEFAULT '',
            service_item TEXT NOT NULL DEFAULT '',
            service_issue TEXT NOT NULL DEFAULT '',
            manager_approval_name TEXT NOT NULL DEFAULT '',
            manager_approval_date TEXT NOT NULL DEFAULT '',
            return_for_credit TEXT NOT NULL DEFAULT '',
            service_record_id TEXT NOT NULL DEFAULT '',
            linked_contract_number TEXT NOT NULL DEFAULT '',
            linked_sale_record_id TEXT NOT NULL DEFAULT '',
            extracted_document_summary TEXT NOT NULL DEFAULT '',
            extracted_product_type TEXT NOT NULL DEFAULT '',
            extracted_color TEXT NOT NULL DEFAULT '',
            extracted_configuration TEXT NOT NULL DEFAULT '',
            extracted_measurements TEXT NOT NULL DEFAULT '',
            extracted_accessories TEXT NOT NULL DEFAULT '',
            extracted_notes TEXT NOT NULL DEFAULT '',
            extracted_special_requirements TEXT NOT NULL DEFAULT '',
            extracted_confidence_flags TEXT NOT NULL DEFAULT '',
            detail_checklist TEXT NOT NULL DEFAULT '',
            confirmed_measurements TEXT NOT NULL DEFAULT '',
            confirmed_layout TEXT NOT NULL DEFAULT '',
            confirmed_product_match TEXT NOT NULL DEFAULT '',
            confirmed_accessories TEXT NOT NULL DEFAULT '',
            confirmed_customer_expectations TEXT NOT NULL DEFAULT '',
            discrepancies_found TEXT NOT NULL DEFAULT '',
            discrepancy_category TEXT NOT NULL DEFAULT '',
            discrepancy_notes TEXT NOT NULL DEFAULT '',
            changes_needed TEXT NOT NULL DEFAULT '',
            ready_for_install TEXT NOT NULL DEFAULT '',
            follow_up_required TEXT NOT NULL DEFAULT '',
            install_handoff_summary TEXT NOT NULL DEFAULT '',
            created_by_user_id INTEGER,
            updated_by_user_id INTEGER,
            completion_notes TEXT NOT NULL DEFAULT '',
            completion_work_performed TEXT NOT NULL DEFAULT '',
            completion_recipient_name TEXT NOT NULL DEFAULT '',
            completion_recipient_email TEXT NOT NULL DEFAULT '',
            completion_email_subject TEXT NOT NULL DEFAULT '',
            completion_email_body TEXT NOT NULL DEFAULT '',
            completed_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            completed_by_user_id INTEGER,
            completion_email_sent_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (assigned_user_id) REFERENCES users(id),
            FOREIGN KEY (created_by_user_id) REFERENCES users(id),
            FOREIGN KEY (updated_by_user_id) REFERENCES users(id),
            FOREIGN KEY (completed_by_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS job_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            content_type TEXT NOT NULL DEFAULT '',
            file_size INTEGER NOT NULL DEFAULT 0,
            uploaded_by_user_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS job_part_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            required_quantity INTEGER NOT NULL,
            pulled_quantity INTEGER NOT NULL DEFAULT 0,
            created_by_user_id INTEGER,
            updated_by_user_id INTEGER,
            updated_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (part_id) REFERENCES parts(id),
            FOREIGN KEY (created_by_user_id) REFERENCES users(id),
            FOREIGN KEY (updated_by_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS job_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            note_author_user_id INTEGER,
            note_author TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT '',
            updated_by_user_id INTEGER,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (note_author_user_id) REFERENCES users(id),
            FOREIGN KEY (updated_by_user_id) REFERENCES users(id)
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

        CREATE TABLE IF NOT EXISTS app_counters (
            name TEXT PRIMARY KEY,
            current_value INTEGER NOT NULL
        );
        """
    )
    db.commit()


def ensure_optional_columns(db: sqlite3.Connection) -> None:
    warehouse_columns = {row["name"] for row in db.execute("PRAGMA table_info(warehouses)")}
    if "is_active" not in warehouse_columns:
        db.execute("ALTER TABLE warehouses ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

    part_columns = {row["name"] for row in db.execute("PRAGMA table_info(parts)")}
    if "scan_code" not in part_columns:
        db.execute("ALTER TABLE parts ADD COLUMN scan_code TEXT NOT NULL DEFAULT ''")
    if "item_type" not in part_columns:
        db.execute("ALTER TABLE parts ADD COLUMN item_type TEXT NOT NULL DEFAULT 'stocked'")
    if "created_by_user_id" not in part_columns:
        db.execute("ALTER TABLE parts ADD COLUMN created_by_user_id INTEGER")
    if "updated_by_user_id" not in part_columns:
        db.execute("ALTER TABLE parts ADD COLUMN updated_by_user_id INTEGER")
    if "created_at" not in part_columns:
        db.execute("ALTER TABLE parts ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
    if "updated_at" not in part_columns:
        db.execute("ALTER TABLE parts ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")

    job_columns = {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}
    if "customer_name" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN customer_name TEXT NOT NULL DEFAULT ''")
    if "address" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN address TEXT NOT NULL DEFAULT ''")
    if "scheduled_for" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN scheduled_for TEXT NOT NULL DEFAULT ''")
    if "job_type" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN job_type TEXT NOT NULL DEFAULT ''")
    if "assigned_user_id" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN assigned_user_id INTEGER")
    service_job_columns = {
        "service_code": "TEXT NOT NULL DEFAULT ''",
        "office_number": "TEXT NOT NULL DEFAULT ''",
        "zone_number": "TEXT NOT NULL DEFAULT ''",
        "contract_number": "TEXT NOT NULL DEFAULT ''",
        "call_date": "TEXT NOT NULL DEFAULT ''",
        "scheduled_time": "TEXT NOT NULL DEFAULT ''",
        "estimated_hours": "TEXT NOT NULL DEFAULT ''",
        "prior_visit_count": "INTEGER NOT NULL DEFAULT 0",
        "customer_name_primary": "TEXT NOT NULL DEFAULT ''",
        "customer_name_secondary": "TEXT NOT NULL DEFAULT ''",
        "address_line_1": "TEXT NOT NULL DEFAULT ''",
        "city": "TEXT NOT NULL DEFAULT ''",
        "state": "TEXT NOT NULL DEFAULT ''",
        "zip": "TEXT NOT NULL DEFAULT ''",
        "primary_phone": "TEXT NOT NULL DEFAULT ''",
        "secondary_phone": "TEXT NOT NULL DEFAULT ''",
        "email": "TEXT NOT NULL DEFAULT ''",
        "best_contact_note": "TEXT NOT NULL DEFAULT ''",
        "sale_date": "TEXT NOT NULL DEFAULT ''",
        "salesperson": "TEXT NOT NULL DEFAULT ''",
        "install_date": "TEXT NOT NULL DEFAULT ''",
        "product_type": "TEXT NOT NULL DEFAULT ''",
        "color": "TEXT NOT NULL DEFAULT ''",
        "customer_complaint": "TEXT NOT NULL DEFAULT ''",
        "dispatch_description": "TEXT NOT NULL DEFAULT ''",
        "probable_issue_category": "TEXT NOT NULL DEFAULT ''",
        "service_category": "TEXT NOT NULL DEFAULT ''",
        "urgency": "TEXT NOT NULL DEFAULT ''",
        "internal_notes": "TEXT NOT NULL DEFAULT ''",
        "return_trip_required": "TEXT NOT NULL DEFAULT ''",
        "return_reason": "TEXT NOT NULL DEFAULT ''",
        "return_estimated_hours": "TEXT NOT NULL DEFAULT ''",
        "survey_left": "TEXT NOT NULL DEFAULT ''",
        "parts_to_order": "TEXT NOT NULL DEFAULT ''",
        "service_cost": "TEXT NOT NULL DEFAULT ''",
        "payment_method": "TEXT NOT NULL DEFAULT ''",
        "no_payment_due": "TEXT NOT NULL DEFAULT ''",
        "start_time": "TEXT NOT NULL DEFAULT ''",
        "end_time": "TEXT NOT NULL DEFAULT ''",
        "travel_time_minutes": "INTEGER NOT NULL DEFAULT 0",
        "total_time_minutes": "INTEGER NOT NULL DEFAULT 0",
        "customer_comments": "TEXT NOT NULL DEFAULT ''",
        "customer_signature": "TEXT NOT NULL DEFAULT ''",
        "paid_service": "TEXT NOT NULL DEFAULT ''",
        "service_fault_category": "TEXT NOT NULL DEFAULT ''",
        "service_item": "TEXT NOT NULL DEFAULT ''",
        "service_issue": "TEXT NOT NULL DEFAULT ''",
        "manager_approval_name": "TEXT NOT NULL DEFAULT ''",
        "manager_approval_date": "TEXT NOT NULL DEFAULT ''",
        "return_for_credit": "TEXT NOT NULL DEFAULT ''",
        "service_record_id": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, column_sql in service_job_columns.items():
        if column_name not in job_columns:
            db.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_sql}")
    detail_job_columns = {
        "linked_contract_number": "TEXT NOT NULL DEFAULT ''",
        "linked_sale_record_id": "TEXT NOT NULL DEFAULT ''",
        "extracted_document_summary": "TEXT NOT NULL DEFAULT ''",
        "extracted_product_type": "TEXT NOT NULL DEFAULT ''",
        "extracted_color": "TEXT NOT NULL DEFAULT ''",
        "extracted_configuration": "TEXT NOT NULL DEFAULT ''",
        "extracted_measurements": "TEXT NOT NULL DEFAULT ''",
        "extracted_accessories": "TEXT NOT NULL DEFAULT ''",
        "extracted_notes": "TEXT NOT NULL DEFAULT ''",
        "extracted_special_requirements": "TEXT NOT NULL DEFAULT ''",
        "extracted_confidence_flags": "TEXT NOT NULL DEFAULT ''",
        "detail_checklist": "TEXT NOT NULL DEFAULT ''",
        "confirmed_measurements": "TEXT NOT NULL DEFAULT ''",
        "confirmed_layout": "TEXT NOT NULL DEFAULT ''",
        "confirmed_product_match": "TEXT NOT NULL DEFAULT ''",
        "confirmed_accessories": "TEXT NOT NULL DEFAULT ''",
        "confirmed_customer_expectations": "TEXT NOT NULL DEFAULT ''",
        "discrepancies_found": "TEXT NOT NULL DEFAULT ''",
        "discrepancy_category": "TEXT NOT NULL DEFAULT ''",
        "discrepancy_notes": "TEXT NOT NULL DEFAULT ''",
        "changes_needed": "TEXT NOT NULL DEFAULT ''",
        "ready_for_install": "TEXT NOT NULL DEFAULT ''",
        "follow_up_required": "TEXT NOT NULL DEFAULT ''",
        "install_handoff_summary": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, column_sql in detail_job_columns.items():
        if column_name not in job_columns:
            db.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_sql}")
    if "completion_notes" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN completion_notes TEXT NOT NULL DEFAULT ''")
    if "completion_work_performed" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN completion_work_performed TEXT NOT NULL DEFAULT ''")
    if "completion_recipient_name" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN completion_recipient_name TEXT NOT NULL DEFAULT ''")
    if "completion_recipient_email" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN completion_recipient_email TEXT NOT NULL DEFAULT ''")
    if "completion_email_subject" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN completion_email_subject TEXT NOT NULL DEFAULT ''")
    if "completion_email_body" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN completion_email_body TEXT NOT NULL DEFAULT ''")
    if "completed_at" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN completed_at TEXT NOT NULL DEFAULT ''")
    if "completion_email_sent_at" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN completion_email_sent_at TEXT NOT NULL DEFAULT ''")
    if "created_by_user_id" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN created_by_user_id INTEGER")
    if "updated_by_user_id" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN updated_by_user_id INTEGER")
    if "updated_at" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
    if "completed_by_user_id" not in job_columns:
        db.execute("ALTER TABLE jobs ADD COLUMN completed_by_user_id INTEGER")

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS role_permissions (
            role TEXT PRIMARY KEY,
            inventory_access INTEGER NOT NULL DEFAULT 0,
            job_access INTEGER NOT NULL DEFAULT 0,
            purchase_orders_access INTEGER NOT NULL DEFAULT 0,
            receiving_access INTEGER NOT NULL DEFAULT 0,
            notes_access INTEGER NOT NULL DEFAULT 0,
            user_management INTEGER NOT NULL DEFAULT 0,
            reporting_access INTEGER NOT NULL DEFAULT 0,
            receive_jobs INTEGER NOT NULL DEFAULT 0,
            complete_jobs INTEGER NOT NULL DEFAULT 0,
            edit_records INTEGER NOT NULL DEFAULT 0,
            delete_records INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        """
    )

    order_list_columns = {row["name"] for row in db.execute("PRAGMA table_info(order_list_items)")}
    if "created_by_user_id" not in order_list_columns:
        db.execute("ALTER TABLE order_list_items ADD COLUMN created_by_user_id INTEGER")
    if "updated_by_user_id" not in order_list_columns:
        db.execute("ALTER TABLE order_list_items ADD COLUMN updated_by_user_id INTEGER")

    order_form_template_columns = {row["name"] for row in db.execute("PRAGMA table_info(order_form_templates)")}
    if not order_form_template_columns:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS order_form_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                form_variant TEXT NOT NULL DEFAULT 'bathbuild',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT ''
            );
            """
        )
    vendor_columns = {row["name"] for row in db.execute("PRAGMA table_info(vendors)")}
    if "linked_template_id" not in vendor_columns:
        db.execute("ALTER TABLE vendors ADD COLUMN linked_template_id TEXT NOT NULL DEFAULT ''")

    purchase_order_columns = {row["name"] for row in db.execute("PRAGMA table_info(purchase_orders)")}
    if "template_id" not in purchase_order_columns:
        db.execute("ALTER TABLE purchase_orders ADD COLUMN template_id TEXT NOT NULL DEFAULT ''")
    if "eta" not in purchase_order_columns:
        db.execute("ALTER TABLE purchase_orders ADD COLUMN eta TEXT NOT NULL DEFAULT ''")
    if "notes" not in purchase_order_columns:
        db.execute("ALTER TABLE purchase_orders ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
    if "updated_at" not in purchase_order_columns:
        db.execute("ALTER TABLE purchase_orders ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
    if "created_by_user_id" not in purchase_order_columns:
        db.execute("ALTER TABLE purchase_orders ADD COLUMN created_by_user_id INTEGER")
    if "updated_by_user_id" not in purchase_order_columns:
        db.execute("ALTER TABLE purchase_orders ADD COLUMN updated_by_user_id INTEGER")

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS purchase_order_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_order_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            quantity_ordered INTEGER NOT NULL,
            quantity_received INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
            FOREIGN KEY (part_id) REFERENCES parts(id)
        );

        CREATE TABLE IF NOT EXISTS order_list_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            vendor_id INTEGER NOT NULL,
            template_id TEXT NOT NULL DEFAULT '',
            quantity_requested INTEGER NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (part_id) REFERENCES parts(id),
            FOREIGN KEY (vendor_id) REFERENCES vendors(id)
        );

        CREATE TABLE IF NOT EXISTS job_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            note_author_user_id INTEGER,
            note_author TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT '',
            updated_by_user_id INTEGER,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (note_author_user_id) REFERENCES users(id),
            FOREIGN KEY (updated_by_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS job_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            content_type TEXT NOT NULL DEFAULT '',
            file_size INTEGER NOT NULL DEFAULT 0,
            uploaded_by_user_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id)
        );
        """
    )

    requirement_columns = {row["name"] for row in db.execute("PRAGMA table_info(job_part_requirements)")}
    if "created_by_user_id" not in requirement_columns:
        db.execute("ALTER TABLE job_part_requirements ADD COLUMN created_by_user_id INTEGER")
    if "updated_by_user_id" not in requirement_columns:
        db.execute("ALTER TABLE job_part_requirements ADD COLUMN updated_by_user_id INTEGER")
    if "updated_at" not in requirement_columns:
        db.execute("ALTER TABLE job_part_requirements ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")

    receiving_columns = {row["name"] for row in db.execute("PRAGMA table_info(receiving_logs)")}
    if "checked_in_by_user_id" not in receiving_columns:
        db.execute("ALTER TABLE receiving_logs ADD COLUMN checked_in_by_user_id INTEGER")
    if "checked_in_at" not in receiving_columns:
        db.execute("ALTER TABLE receiving_logs ADD COLUMN checked_in_at TEXT NOT NULL DEFAULT ''")

    usage_columns = {row["name"] for row in db.execute("PRAGMA table_info(usage_logs)")}
    if "created_by_user_id" not in usage_columns:
        db.execute("ALTER TABLE usage_logs ADD COLUMN created_by_user_id INTEGER")

    db.execute("UPDATE jobs SET customer_name = 'Demo Customer ' || job_number WHERE TRIM(customer_name) = ''")
    db.execute("UPDATE jobs SET address = 'Address pending for ' || job_number WHERE TRIM(address) = ''")
    db.execute("UPDATE jobs SET scheduled_for = DATE(created_at) WHERE TRIM(scheduled_for) = ''")
    db.execute("UPDATE jobs SET job_type = title WHERE TRIM(COALESCE(job_type, '')) = ''")
    db.execute("UPDATE jobs SET completed_at = created_at WHERE status = 'Completed' AND TRIM(completed_at) = ''")
    db.execute("UPDATE jobs SET updated_at = created_at WHERE TRIM(updated_at) = ''")
    db.execute("UPDATE parts SET created_at = COALESCE(created_at, '')")
    db.execute("UPDATE parts SET updated_at = created_at WHERE TRIM(updated_at) = ''")
    db.execute("UPDATE parts SET created_at = DATETIME('now') WHERE TRIM(created_at) = ''")
    sync_job_assigned_users(db)
    ensure_default_role_permissions(db)
    db.execute("UPDATE purchase_orders SET updated_at = created_at WHERE TRIM(updated_at) = ''")
    db.execute("UPDATE receiving_logs SET checked_in_at = created_at WHERE TRIM(checked_in_at) = ''")
    db.execute("UPDATE parts SET scan_code = UPPER(TRIM(part_number)) WHERE TRIM(scan_code) = ''")
    db.execute("UPDATE parts SET scan_code = UPPER(TRIM(scan_code)) WHERE TRIM(scan_code) != ''")
    db.execute("UPDATE parts SET item_type = 'stocked' WHERE TRIM(COALESCE(item_type, '')) = ''")
    db.execute("UPDATE parts SET item_type = LOWER(item_type)")
    db.execute("UPDATE parts SET item_type = 'stocked' WHERE item_type NOT IN ('stocked', 'non_stock')")
    db.execute("CREATE INDEX IF NOT EXISTS idx_parts_scan_code ON parts (warehouse_id, scan_code)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_assigned_user_id ON jobs (assigned_user_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_job_attachments_job_id ON job_attachments (job_id, created_at)")

    if db.execute("SELECT COUNT(*) AS count FROM order_form_templates").fetchone()["count"] == 0:
        now_iso = datetime.now().isoformat()
        db.executemany(
            "INSERT INTO order_form_templates (template_id, name, form_variant, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("aquaflow-standard", "AquaFlow Standard Requisition", "aquaflow", "Placeholder template for AquaFlow scanned form workflow", now_iso, now_iso),
                ("bathbuild-standard", "BathBuild Standard Requisition", "bathbuild", "Placeholder template for BathBuild scanned form workflow", now_iso, now_iso),
                ("universal-service", "Universal Service Order", "bathbuild", "General-purpose placeholder form for new vendors", now_iso, now_iso),
            ],
        )
    db.execute("UPDATE vendors SET linked_template_id = 'aquaflow-standard' WHERE linked_template_id = '' AND name LIKE '%AquaFlow%'")
    db.execute("UPDATE vendors SET linked_template_id = 'bathbuild-standard' WHERE linked_template_id = '' AND name LIKE '%BathBuild%'")

    legacy_pos = db.execute(
        """
        SELECT id, part_id, quantity, received_quantity, created_at, updated_at, notes
        FROM purchase_orders
        WHERE part_id IS NOT NULL
          AND id NOT IN (SELECT DISTINCT purchase_order_id FROM purchase_order_lines)
        """
    ).fetchall()
    for po in legacy_pos:
        db.execute(
            """
            INSERT INTO purchase_order_lines (
                purchase_order_id, part_id, quantity_ordered, quantity_received, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                po["id"],
                po["part_id"],
                po["quantity"] or 0,
                po["received_quantity"] or 0,
                po["notes"] or '',
                po["created_at"],
                po["updated_at"] or po["created_at"],
            ),
        )

    sync_purchase_order_rollups(db)
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


def ensure_app_counters(db: sqlite3.Connection) -> None:
    row = db.execute(
        """
        SELECT MAX(CAST(SUBSTR(po_number, 4) AS INTEGER)) AS max_po_number
        FROM purchase_orders
        WHERE po_number LIKE 'PO-%'
        """
    ).fetchone()
    max_po_number = int(row["max_po_number"] or 1000)
    existing = db.execute("SELECT current_value FROM app_counters WHERE name = 'po_number'").fetchone()
    if existing is None:
        db.execute(
            "INSERT INTO app_counters (name, current_value) VALUES ('po_number', ?)",
            (max_po_number,),
        )
        return
    if int(existing["current_value"]) < max_po_number:
        db.execute(
            "UPDATE app_counters SET current_value = ? WHERE name = 'po_number'",
            (max_po_number,),
        )


def ensure_default_users(db: sqlite3.Connection) -> None:
    if int(db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"] or 0) > 0:
        return
    now_iso = datetime.now().isoformat()
    default_password = "55555"
    users = [
        ("manager", generate_password_hash(default_password), "Operations Manager", ROLE_MANAGER, 1, now_iso),
        ("dal.install", generate_password_hash(default_password), "Dallas Install Crew A", ROLE_INSTALLER, 1, now_iso),
        ("dal.service", generate_password_hash(default_password), "Dallas Repair Crew B", ROLE_SERVICE_TECH, 1, now_iso),
        ("chi.install", generate_password_hash(default_password), "Chicago Install Crew A", ROLE_INSTALLER, 1, now_iso),
        ("chi.service", generate_password_hash(default_password), "Chicago Service Crew B", ROLE_SERVICE_TECH, 1, now_iso),
        ("phx.install", generate_password_hash(default_password), "Phoenix Install Crew A", ROLE_INSTALLER, 1, now_iso),
        ("phx.service", generate_password_hash(default_password), "Phoenix Service Crew B", ROLE_SERVICE_TECH, 1, now_iso),
    ]
    db.executemany(
        "INSERT INTO users (username, password_hash, display_name, role, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        users,
    )


def ensure_default_role_permissions(db: sqlite3.Connection) -> None:
    existing_roles = {row["role"] for row in db.execute("SELECT role FROM role_permissions").fetchall()}
    for role, permissions in DEFAULT_ROLE_PERMISSIONS.items():
        if role in existing_roles:
            continue
        db.execute(
            """
            INSERT INTO role_permissions (
                role, inventory_access, job_access, purchase_orders_access, receiving_access, notes_access,
                user_management, reporting_access, receive_jobs, complete_jobs, edit_records, delete_records
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                role,
                int(permissions["inventory_access"]),
                int(permissions["job_access"]),
                int(permissions["purchase_orders_access"]),
                int(permissions["receiving_access"]),
                int(permissions["notes_access"]),
                int(permissions["user_management"]),
                int(permissions["reporting_access"]),
                int(permissions["receive_jobs"]),
                int(permissions["complete_jobs"]),
                int(permissions["edit_records"]),
                int(permissions["delete_records"]),
            ),
        )


def sync_job_assigned_users(db: sqlite3.Connection) -> None:
    db.execute(
        """
        UPDATE jobs
        SET assigned_user_id = (
            SELECT users.id
            FROM users
            WHERE users.display_name = jobs.technician
            LIMIT 1
        )
        WHERE assigned_user_id IS NULL
        """
    )


def begin_immediate_transaction(db: sqlite3.Connection) -> None:
    db.execute("BEGIN IMMEDIATE")


def serialize_user(row: sqlite3.Row | dict | None) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    return {
        "id": int(data["id"]),
        "username": str(data["username"]),
        "display_name": str(data["display_name"]),
        "role": str(data["role"]),
        "is_active": bool(data.get("is_active", 1)),
    }


def serialize_job_attachment(row: sqlite3.Row | dict | None) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    return {
        "id": int(data["id"]),
        "job_id": int(data["job_id"]),
        "original_name": str(data["original_name"]),
        "stored_name": str(data["stored_name"]),
        "content_type": str(data.get("content_type", "")),
        "file_size": int(data.get("file_size") or 0),
        "uploaded_by_user_id": int(data["uploaded_by_user_id"]) if data.get("uploaded_by_user_id") is not None else None,
        "uploaded_by_name": str(data.get("uploaded_by_name") or ""),
        "created_at": str(data.get("created_at") or ""),
    }


def serialize_role_permission(row: sqlite3.Row | dict | None) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    return {"role": str(data["role"]), **{key: bool(data.get(key, 0)) for key in PERMISSION_KEYS}}


def current_user_record(db: sqlite3.Connection | None = None) -> sqlite3.Row | None:
    cached = getattr(g, "current_user_row", None)
    if cached is not None:
        return cached
    user_id = session.get("user_id")
    if not user_id:
        g.current_user_row = None
        return None
    target_db = db or get_db()
    row = target_db.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (int(user_id),)).fetchone()
    if row is None:
        session.pop("user_id", None)
    g.current_user_row = row
    return row


def current_user_is_manager(db: sqlite3.Connection | None = None) -> bool:
    user = current_user_record(db)
    return bool(user and str(user["role"]) in {ROLE_MANAGER, ROLE_ADMIN})


def role_permissions(db: sqlite3.Connection, role: str) -> dict[str, bool]:
    row = db.execute("SELECT * FROM role_permissions WHERE role = ?", (role,)).fetchone()
    if row is None:
        fallback = DEFAULT_ROLE_PERMISSIONS.get(role, {})
        return {key: bool(fallback.get(key, 0)) for key in PERMISSION_KEYS}
    return {key: bool(row[key]) for key in PERMISSION_KEYS}


def current_user_can(permission: str, db: sqlite3.Connection | None = None) -> bool:
    user = current_user_record(db)
    if user is None:
        return False
    if str(user["role"]) == ROLE_ADMIN:
        return True
    permissions = role_permissions(db or get_db(), str(user["role"]))
    return bool(permissions.get(permission, False))


def all_role_permissions(db: sqlite3.Connection) -> list[dict]:
    return [
        serialize_role_permission(row)
        for row in db.execute("SELECT * FROM role_permissions ORDER BY role").fetchall()
    ]


def current_user_id(db: sqlite3.Connection | None = None) -> int | None:
    user = current_user_record(db)
    return int(user["id"]) if user is not None else None


def auth_error(message: str, status_code: int) -> tuple:
    return jsonify({"error": message, "authRequired": status_code == 401}), status_code


def log_server_error(error: Exception, context: str, **details) -> None:
    app.logger.exception(
        "%s failed | path=%s | method=%s | details=%s",
        context,
        request.path if request else "",
        request.method if request else "",
        details,
        exc_info=error,
    )


def handle_api_exception(error: Exception, context: str = "API request"):
    log_server_error(error, context)
    if isinstance(error, HTTPException):
        message = error.description or "Request failed."
        return jsonify({"error": message, "authRequired": error.code == 401}), int(error.code or 500)
    return jsonify({"error": "Something went wrong in that feature. The rest of the app should still be usable."}), 500


def safe_feature_load(label: str, default_value, loader):
    try:
        return loader()
    except Exception as error:
        app.logger.exception("Feature load failed for %s", label, exc_info=error)
        return default_value


def login_required(route_fn):
    @wraps(route_fn)
    def wrapper(*args, **kwargs):
        if current_user_record() is None:
            return auth_error("Sign in required.", 401)
        try:
            return route_fn(*args, **kwargs)
        except Exception as error:
            return handle_api_exception(error, route_fn.__name__)

    return wrapper


def manager_required(route_fn):
    @wraps(route_fn)
    def wrapper(*args, **kwargs):
        user = current_user_record()
        if user is None:
            return auth_error("Sign in required.", 401)
        if str(user["role"]) not in {ROLE_MANAGER, ROLE_ADMIN}:
            return auth_error("Manager access required.", 403)
        try:
            return route_fn(*args, **kwargs)
        except Exception as error:
            return handle_api_exception(error, route_fn.__name__)

    return wrapper


def permission_required(permission: str):
    def decorator(route_fn):
        @wraps(route_fn)
        def wrapper(*args, **kwargs):
            user = current_user_record()
            if user is None:
                return auth_error("Sign in required.", 401)
            if not current_user_can(permission):
                return auth_error("You do not have permission for that action.", 403)
            try:
                return route_fn(*args, **kwargs)
            except Exception as error:
                return handle_api_exception(error, route_fn.__name__)

        return wrapper

    return decorator


def manager_or_assigned_job(job: sqlite3.Row | None) -> bool:
    user = current_user_record()
    if user is None or job is None:
        return False
    if str(user["role"]) in GLOBAL_JOB_ACCESS_ROLES and current_user_can("job_access"):
        return True
    return int(job["assigned_user_id"] or 0) == int(user["id"])


def require_assignable_user(db: sqlite3.Connection, assigned_user_id: int | None) -> sqlite3.Row | None:
    if not assigned_user_id:
        return None
    return db.execute(
        "SELECT * FROM users WHERE id = ? AND is_active = 1 AND role IN (?, ?)",
        (int(assigned_user_id), ROLE_INSTALLER, ROLE_SERVICE_TECH),
    ).fetchone()


def job_with_access(db: sqlite3.Connection, job_id: int, warehouse_id: int | None = None) -> sqlite3.Row | None:
    params: list[object] = [job_id]
    warehouse_filter = ""
    if warehouse_id is not None:
        warehouse_filter = " AND jobs.warehouse_id = ?"
        params.append(warehouse_id)
    row = db.execute(
        f"""
        SELECT jobs.*, users.display_name AS assigned_user_name
        FROM jobs
        LEFT JOIN users ON users.id = jobs.assigned_user_id
        WHERE jobs.id = ?{warehouse_filter}
        """,
        tuple(params),
    ).fetchone()
    if row is None or not manager_or_assigned_job(row):
        return None
    return row


def related_service_job_rows(
    db: sqlite3.Connection,
    warehouse_id: int,
    contract_number: str = "",
    customer_name: str = "",
    address: str = "",
    exclude_job_id: int | None = None,
) -> list[sqlite3.Row]:
    rows_found = [
        row
        for row in db.execute(
            """
            SELECT *
            FROM jobs
            WHERE warehouse_id = ?
              AND job_type IN ('Service', 'Warranty')
            ORDER BY datetime(COALESCE(completed_at, created_at)) DESC
            """,
            (warehouse_id,),
        ).fetchall()
    ]
    matches: list[sqlite3.Row] = []
    contract_key = contract_number.strip().lower()
    customer_key = customer_name.strip().lower()
    address_key = address.strip().lower()
    for row in rows_found:
        if exclude_job_id is not None and int(row["id"]) == int(exclude_job_id):
            continue
        row_contract = str(row["contract_number"] or "").strip().lower()
        row_customer = str(row["customer_name_primary"] or row["customer_name"] or "").strip().lower()
        row_address = str(row["address_line_1"] or row["address"] or "").strip().lower()
        contract_match = bool(contract_key and row_contract and row_contract == contract_key)
        customer_match = bool(customer_key and row_customer and row_customer == customer_key)
        address_match = bool(address_key and row_address and row_address == address_key)
        if contract_match or (customer_match and address_match) or (not contract_key and address_match):
            matches.append(row)
    return matches


def prior_service_visit_count(
    db: sqlite3.Connection,
    warehouse_id: int,
    contract_number: str = "",
    customer_name: str = "",
    address: str = "",
    exclude_job_id: int | None = None,
) -> int:
    return len(
        related_service_job_rows(
            db,
            warehouse_id,
            contract_number=contract_number,
            customer_name=customer_name,
            address=address,
            exclude_job_id=exclude_job_id,
        )
    )


def related_install_context(
    db: sqlite3.Connection, warehouse_id: int, contract_number: str = "", customer_name: str = "", address: str = ""
) -> sqlite3.Row | None:
    install_rows = [
        row
        for row in db.execute(
            """
            SELECT *
            FROM jobs
            WHERE warehouse_id = ?
              AND job_type = 'Install'
            ORDER BY datetime(COALESCE(completed_at, created_at)) DESC
            """,
            (warehouse_id,),
        ).fetchall()
    ]
    contract_key = contract_number.strip().lower()
    customer_key = customer_name.strip().lower()
    address_key = address.strip().lower()
    for row in install_rows:
        row_contract = str(row["contract_number"] or "").strip().lower()
        row_customer = str(row["customer_name_primary"] or row["customer_name"] or "").strip().lower()
        row_address = str(row["address_line_1"] or row["address"] or "").strip().lower()
        if contract_key and row_contract == contract_key:
            return row
        if customer_key and address_key and row_customer == customer_key and row_address == address_key:
            return row
        if address_key and row_address == address_key:
            return row
    return None


def requirement_with_access(db: sqlite3.Connection, requirement_id: int) -> sqlite3.Row | None:
    row = requirement_with_context(db, requirement_id)
    if row is None:
        return None
    if not manager_or_assigned_job(row):
        return None
    return row


def attachment_storage_dir(job_id: int) -> Path:
    path = ATTACHMENTS_DIR / f"job_{int(job_id)}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def allowed_attachment(filename: str) -> bool:
    suffix = Path(filename).suffix.lower()
    return suffix in ALLOWED_ATTACHMENT_EXTENSIONS


def store_job_attachment(file_storage, job_id: int) -> tuple[Path, str, int]:
    original_name = secure_filename(file_storage.filename or "").strip()
    if not original_name:
        raise ValueError("Choose a file to upload.")
    if not allowed_attachment(original_name):
        raise ValueError("That file type is not supported.")

    payload = file_storage.read()
    if not payload:
        raise ValueError("The selected file is empty.")
    if len(payload) > MAX_ATTACHMENT_BYTES:
        raise ValueError("Files must be 15 MB or smaller.")

    suffix = Path(original_name).suffix.lower()
    stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex}{suffix}"
    destination = attachment_storage_dir(job_id) / stored_name
    destination.write_bytes(payload)
    return destination, original_name, len(payload)


def attachment_with_access(db: sqlite3.Connection, attachment_id: int) -> sqlite3.Row | None:
    row = db.execute(
        """
        SELECT job_attachments.*, jobs.warehouse_id, jobs.assigned_user_id
        FROM job_attachments
        JOIN jobs ON jobs.id = job_attachments.job_id
        WHERE job_attachments.id = ?
        """,
        (attachment_id,),
    ).fetchone()
    if row is None or not manager_or_assigned_job(row):
        return None
    return row


def job_attachment_rows(db: sqlite3.Connection, job_id: int) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT job_attachments.*, users.display_name AS uploaded_by_name
        FROM job_attachments
        LEFT JOIN users ON users.id = job_attachments.uploaded_by_user_id
        WHERE job_attachments.job_id = ?
        ORDER BY datetime(job_attachments.created_at) DESC
        """,
        (job_id,),
    ).fetchall()


def completion_usage_rows(db: sqlite3.Connection, job: sqlite3.Row) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT usage_logs.*, parts.part_number, parts.description
        FROM usage_logs
        JOIN parts ON parts.id = usage_logs.part_id
        WHERE usage_logs.warehouse_id = ? AND usage_logs.job_number = ?
        ORDER BY datetime(usage_logs.created_at) ASC
        """,
        (int(job["warehouse_id"]), str(job["job_number"])),
    ).fetchall()


def completion_requirements(db: sqlite3.Connection, job_id: int) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT job_part_requirements.*, parts.part_number, parts.description, parts.item_type
        FROM job_part_requirements
        JOIN parts ON parts.id = job_part_requirements.part_id
        WHERE job_part_requirements.job_id = ?
        ORDER BY parts.part_number
        """,
        (job_id,),
    ).fetchall()


def build_completion_preview(
    db: sqlite3.Connection,
    job: sqlite3.Row,
    recipient_name: str,
    recipient_email: str,
    work_performed: str,
    completion_notes: str,
) -> dict:
    requirements = completion_requirements(db, int(job["id"]))
    attachments = [serialize_job_attachment(row) for row in job_attachment_rows(db, int(job["id"]))]
    usage_rows = completion_usage_rows(db, job)
    part_lines = [
        {
            "partNumber": str(row["part_number"]),
            "description": str(row["description"]),
            "requiredQuantity": int(row["required_quantity"]),
            "pulledQuantity": int(row["pulled_quantity"]),
            "remainingQuantity": max(int(row["required_quantity"]) - int(row["pulled_quantity"]), 0),
            "itemType": str(row["item_type"]),
        }
        for row in requirements
    ]
    usage_lines = [
        {
            "partNumber": str(row["part_number"]),
            "description": str(row["description"]),
            "quantity": int(row["quantity"]),
            "notes": str(row["notes"]),
            "createdAt": str(row["created_at"]),
        }
        for row in usage_rows
    ]

    subject = f"Job Complete: {job['job_number']} - {job['customer_name'] or job['title']}"
    body_lines = [
        f"Hello {recipient_name or 'team'},",
        "",
        f"This is the completion summary for job {job['job_number']}.",
        "",
        "Job details:",
        f"- Customer: {job['customer_name'] or 'Not provided'}",
        f"- Address: {job['address'] or 'Not provided'}",
        f"- Job type: {job['job_type'] or job['title']}",
        f"- Technician / Crew: {job['technician']}",
        f"- Scheduled date: {job['scheduled_for'] or 'Not scheduled'}",
        "",
        "Work performed:",
        work_performed or "No work summary was entered.",
        "",
        "Completion notes:",
        completion_notes or "No additional completion notes were entered.",
        "",
        "Parts used / staged for this job:",
    ]
    if part_lines:
        body_lines.extend(
            [
                f"- {item['partNumber']} ({item['description']}): pulled {item['pulledQuantity']} of {item['requiredQuantity']} required"
                for item in part_lines
            ]
        )
    else:
        body_lines.append("- No job parts were recorded.")
    body_lines.extend(["", "Usage log entries:"])
    if usage_lines:
        body_lines.extend(
            [
                f"- {item['partNumber']} qty {item['quantity']} ({item['notes'] or 'No note'})"
                for item in usage_lines
            ]
        )
    else:
        body_lines.append("- No usage log entries were recorded.")
    body_lines.extend(
        [
            "",
            f"Attached files: {len(attachments)}",
            *([f"- {item['original_name']}" for item in attachments] if attachments else ["- No attachments added."]),
            "",
            "Thank you,",
            "Bath Fitters WMS",
        ]
    )

    return {
        "recipientName": recipient_name,
        "recipientEmail": recipient_email,
        "subject": subject,
        "body": "\n".join(body_lines),
        "parts": part_lines,
        "usageLogs": usage_lines,
        "attachments": attachments,
        "sendAvailable": bool(smtp_settings()["enabled"]),
    }


def send_completion_email(preview: dict, job_id: int, attachments: list[sqlite3.Row]) -> None:
    settings = smtp_settings()
    if not settings["enabled"]:
        raise ValueError("Email sending is not configured yet.")

    message = EmailMessage()
    from_label = settings["from_name"]
    from_email = settings["from_email"]
    message["From"] = f"{from_label} <{from_email}>" if from_label else str(from_email)
    message["To"] = str(preview["recipientEmail"])
    message["Subject"] = str(preview["subject"])
    message.set_content(str(preview["body"]))

    for attachment in attachments:
        attachment_path = (BASE_DIR / str(attachment["storage_path"])).resolve()
        try:
            attachment_path.relative_to(ATTACHMENTS_DIR.resolve())
        except ValueError:
            continue
        if not attachment_path.exists():
            continue
        mime_type = str(attachment["content_type"] or mimetypes.guess_type(str(attachment_path))[0] or "application/octet-stream")
        maintype, _, subtype = mime_type.partition("/")
        if not subtype:
            maintype = "application"
            subtype = "octet-stream"
        message.add_attachment(
            attachment_path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=str(attachment["original_name"]),
        )

    with smtplib.SMTP(str(settings["host"]), int(settings["port"])) as smtp:
        smtp.ehlo()
        if bool(settings["use_tls"]):
            smtp.starttls()
            smtp.ehlo()
        if settings["username"]:
            smtp.login(str(settings["username"]), str(settings["password"]))
        smtp.send_message(message)


def all_users(db: sqlite3.Connection) -> list[dict]:
    return [serialize_user(row) for row in db.execute("SELECT * FROM users ORDER BY display_name").fetchall()]


def assigned_worker_users(db: sqlite3.Connection) -> list[dict]:
    return [
        serialize_user(row)
        for row in db.execute(
            "SELECT * FROM users WHERE role IN (?, ?) AND is_active = 1 ORDER BY display_name",
            (ROLE_INSTALLER, ROLE_SERVICE_TECH),
        ).fetchall()
    ]


def refresh_job_status(db: sqlite3.Connection, job_id: int) -> None:
    current_status = db.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if current_status and current_status["status"] == "Completed":
        return
    remaining_requirements = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM job_part_requirements
        WHERE job_id = ? AND pulled_quantity < required_quantity
        """,
        (job_id,),
    ).fetchone()["count"]
    db.execute(
        "UPDATE jobs SET status = ? WHERE id = ?",
        ("Ready to Go" if remaining_requirements == 0 else "Active", job_id),
    )


def has_seed_data(db: sqlite3.Connection) -> bool:
    row = db.execute("SELECT COUNT(*) AS count FROM warehouses").fetchone()
    return bool(row["count"])


def next_po_number(db: sqlite3.Connection) -> str:
    ensure_app_counters(db)
    row = db.execute("SELECT current_value FROM app_counters WHERE name = 'po_number'").fetchone()
    current_value = int(row["current_value"] or 1000) if row else 1000
    next_value = current_value + 1
    db.execute(
        "UPDATE app_counters SET current_value = ? WHERE name = 'po_number'",
        (next_value,),
    )
    return f"PO-{next_value}"


def template_id_for_vendor_name(vendor_name: str) -> str:
    return "aquaflow-standard" if "AquaFlow" in vendor_name else "bathbuild-standard"


def template_record_for_id(db: sqlite3.Connection, template_id: str) -> dict | None:
    if not template_id:
        return None
    row = db.execute("SELECT * FROM order_form_templates WHERE template_id = ?", (template_id,)).fetchone()
    return dict(row) if row else None


def template_id_for_vendor_id(db: sqlite3.Connection, vendor_id: int) -> str:
    row = db.execute("SELECT name, linked_template_id FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
    if row is None:
        return ""
    linked = (row["linked_template_id"] or "").strip()
    return linked or template_id_for_vendor_name(row["name"])


def sync_purchase_order_rollups(db: sqlite3.Connection, po_id: int | None = None) -> None:
    if po_id is None:
        for row in db.execute("SELECT id FROM purchase_orders").fetchall():
            sync_purchase_order_rollups(db, int(row["id"]))
        return

    summary = db.execute(
        """
        SELECT COALESCE(SUM(quantity_ordered), 0) AS quantity_ordered,
               COALESCE(SUM(quantity_received), 0) AS quantity_received,
               MIN(part_id) AS first_part_id
        FROM purchase_order_lines
        WHERE purchase_order_id = ?
        """,
        (po_id,),
    ).fetchone()
    db.execute(
        """
        UPDATE purchase_orders
        SET part_id = ?, quantity = ?, received_quantity = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            summary["first_part_id"],
            int(summary["quantity_ordered"] or 0),
            int(summary["quantity_received"] or 0),
            datetime.now().isoformat(),
            po_id,
        ),
    )


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
                    "scan_code": f"{prefix}-SCAN-{group_index:02d}{item_index:02d}",
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
        DELETE FROM order_list_items;
        DELETE FROM reorder_requests;
        DELETE FROM job_attachments;
        DELETE FROM job_part_requirements;
        DELETE FROM jobs;
        DELETE FROM usage_logs;
        DELETE FROM receiving_logs;
        DELETE FROM stock_transfers;
        DELETE FROM purchase_order_lines;
        DELETE FROM purchase_orders;
        DELETE FROM parts;
        DELETE FROM vendors;
        DELETE FROM role_permissions;
        DELETE FROM users;
        DELETE FROM warehouses;
        DELETE FROM order_form_templates;
        DELETE FROM sqlite_sequence;
        """
    )
    if ATTACHMENTS_DIR.exists():
        for path in ATTACHMENTS_DIR.glob("**/*"):
            if path.is_file():
                path.unlink()

    warehouses = [
        ("Dallas Bath Supply Hub", "DAL"),
        ("Chicago Plumbing Cage", "CHI"),
        ("Phoenix Install Warehouse", "PHX"),
    ]
    db.executemany("INSERT INTO warehouses (name, code, is_active) VALUES (?, ?, 1)", warehouses)

    now_iso = datetime.now().isoformat()
    templates = [
        ("aquaflow-standard", "AquaFlow Standard Requisition", "aquaflow", "Placeholder template for AquaFlow scanned form workflow", now_iso, now_iso),
        ("bathbuild-standard", "BathBuild Standard Requisition", "bathbuild", "Placeholder template for BathBuild scanned form workflow", now_iso, now_iso),
        ("universal-service", "Universal Service Order", "bathbuild", "General-purpose placeholder form for new vendors", now_iso, now_iso),
    ]
    db.executemany(
        "INSERT INTO order_form_templates (template_id, name, form_variant, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        templates,
    )

    vendors = [
        ("AquaFlow Plumbing Supply", "Jordan Ellis", "orders@aquaflow.example", "555-0105", 5, "aquaflow-standard"),
        ("BathBuild Distributors", "Avery Brooks", "sales@bathbuild.example", "555-0138", 3, "bathbuild-standard"),
    ]
    db.executemany(
        "INSERT INTO vendors (name, contact, email, phone, lead_time_days, linked_template_id) VALUES (?, ?, ?, ?, ?, ?)",
        vendors,
    )

    default_password = "55555"
    users = [
        ("manager", generate_password_hash(default_password), "Operations Manager", ROLE_MANAGER, 1, now_iso),
        ("dal.install", generate_password_hash(default_password), "Dallas Install Crew A", ROLE_INSTALLER, 1, now_iso),
        ("dal.service", generate_password_hash(default_password), "Dallas Repair Crew B", ROLE_SERVICE_TECH, 1, now_iso),
        ("chi.install", generate_password_hash(default_password), "Chicago Install Crew A", ROLE_INSTALLER, 1, now_iso),
        ("chi.service", generate_password_hash(default_password), "Chicago Service Crew B", ROLE_SERVICE_TECH, 1, now_iso),
        ("phx.install", generate_password_hash(default_password), "Phoenix Install Crew A", ROLE_INSTALLER, 1, now_iso),
        ("phx.service", generate_password_hash(default_password), "Phoenix Service Crew B", ROLE_SERVICE_TECH, 1, now_iso),
    ]
    db.executemany(
        "INSERT INTO users (username, password_hash, display_name, role, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        users,
    )
    ensure_default_role_permissions(db)

    warehouse_map = {
        row["code"]: row["id"]
        for row in db.execute("SELECT id, code FROM warehouses ORDER BY id").fetchall()
    }
    vendor_map = {
        row["name"]: row["id"]
        for row in db.execute("SELECT id, name FROM vendors ORDER BY id").fetchall()
    }
    user_map = {
        row["display_name"]: row["id"]
        for row in db.execute("SELECT id, display_name FROM users ORDER BY id").fetchall()
    }
    actor_user_id = int(user_map.get("Operations Manager") or 0)

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
                    item["scan_code"],
                    item["description"],
                    item["category"],
                    "stocked",
                    stock,
                    reorder_point,
                    vendor_map[item["vendor_name"]],
                    item["unit_cost"],
                )
            )
    db.executemany(
        """
        INSERT INTO parts
            (warehouse_id, part_number, scan_code, description, category, item_type, stock, reorder_point, vendor_id, unit_cost)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        parts,
    )

    part_map = {
        (row["warehouse_id"], row["part_number"]): row["id"]
        for row in db.execute("SELECT id, warehouse_id, part_number FROM parts").fetchall()
    }

    now = datetime.now()

    completed_demo_jobs = {
        "DAL": [
            {"job_number": "DAL-COMP-301", "title": "Tub-to-shower conversion", "customer_name": "Jordan Blake", "address": "420 Cedar Hollow Dr, Dallas, TX", "scheduled_for": (now - timedelta(days=18)).date().isoformat(), "technician": "Dallas Install Crew A", "notes": "Historic completed conversion with extra trim adjustments.", "days_ago": 18},
            {"job_number": "DAL-COMP-244", "title": "Bathroom repair follow-up", "customer_name": "Noah Patel", "address": "88 Ashview Ln, Dallas, TX", "scheduled_for": (now - timedelta(days=47)).date().isoformat(), "technician": "Dallas Repair Crew B", "notes": "Historic service call with repeat sealant usage.", "days_ago": 47},
            {"job_number": "DAL-COMP-198", "title": "Tub-to-shower conversion", "customer_name": "Mia Foster", "address": "1907 Briar Creek Ct, Dallas, TX", "scheduled_for": (now - timedelta(days=79)).date().isoformat(), "technician": "Dallas Install Crew A", "notes": "Historic conversion with elevated drain and trim usage.", "days_ago": 79},
        ],
        "CHI": [
            {"job_number": "CHI-COMP-388", "title": "Tub-to-shower conversion", "customer_name": "Avery Coleman", "address": "14 N Rockwell Ave, Chicago, IL", "scheduled_for": (now - timedelta(days=22)).date().isoformat(), "technician": "Chicago Install Crew A", "notes": "Historic conversion with extra valve trim pulled.", "days_ago": 22},
            {"job_number": "CHI-COMP-341", "title": "Bathroom repair follow-up", "customer_name": "Elena Ruiz", "address": "512 W Grace St, Chicago, IL", "scheduled_for": (now - timedelta(days=58)).date().isoformat(), "technician": "Chicago Service Crew B", "notes": "Historic repair with repeat drain touch-up usage.", "days_ago": 58},
            {"job_number": "CHI-COMP-295", "title": "Tub-to-shower conversion", "customer_name": "Leo Grant", "address": "6201 W Sunnyside Ave, Chicago, IL", "scheduled_for": (now - timedelta(days=96)).date().isoformat(), "technician": "Chicago Install Crew A", "notes": "Historic conversion with higher wall kit demand.", "days_ago": 96},
        ],
        "PHX": [
            {"job_number": "PHX-COMP-412", "title": "Tub-to-shower conversion", "customer_name": "Nina Chavez", "address": "902 E Juniper Ridge Way, Phoenix, AZ", "scheduled_for": (now - timedelta(days=16)).date().isoformat(), "technician": "Phoenix Install Crew A", "notes": "Historic conversion with extra sealant usage.", "days_ago": 16},
            {"job_number": "PHX-COMP-367", "title": "Bathroom repair follow-up", "customer_name": "Owen Pierce", "address": "3116 S Desert Bloom Rd, Phoenix, AZ", "scheduled_for": (now - timedelta(days=52)).date().isoformat(), "technician": "Phoenix Service Crew B", "notes": "Historic repair with repeat misc usage notes.", "days_ago": 52},
            {"job_number": "PHX-COMP-329", "title": "Tub-to-shower conversion", "customer_name": "Layla Kim", "address": "7745 N Copper Ridge Dr, Phoenix, AZ", "scheduled_for": (now - timedelta(days=104)).date().isoformat(), "technician": "Phoenix Install Crew A", "notes": "Historic conversion with heavier drain kit usage.", "days_ago": 104},
        ],
    }

    demo_jobs = {
        "DAL": [
            {
                "job_number": "DAL-41027",
                "title": "Tub-to-shower conversion",
                "job_type": "Install",
                "customer_name": "Megan Alvarez",
                "address": "1842 N Prairie View Dr, Dallas, TX",
                "scheduled_for": (now + timedelta(days=2)).date().isoformat(),
                "technician": "Dallas Install Crew A",
                "notes": "Need trim kit and drain assembly staged before load-out.",
            },
            {
                "job_number": "DAL-41035",
                "title": "Hall bath wall refresh",
                "job_type": "Install",
                "customer_name": "Darius Quinn",
                "address": "9014 Long Creek Ln, Dallas, TX",
                "scheduled_for": (now + timedelta(days=6)).date().isoformat(),
                "technician": "Dallas Install Crew A",
                "notes": "Install crew needs trim kit and install hardware staged together.",
            },
            {
                "job_number": "DAL-SVC-41031",
                "title": "Bathroom repair follow-up",
                "job_type": "Service",
                "customer_name": "Chris Donnelly",
                "address": "9625 Whisper Bend Ln, Dallas, TX",
                "scheduled_for": (now + timedelta(days=4)).date().isoformat(),
                "technician": "Dallas Repair Crew B",
                "notes": "Sealant and cartridge replacement call.",
            },
            {
                "job_number": "DAL-WAR-41033",
                "title": "Warranty drain adjustment",
                "job_type": "Warranty",
                "customer_name": "Tina Mercer",
                "address": "711 Oak Marsh Ct, Dallas, TX",
                "scheduled_for": (now + timedelta(days=5)).date().isoformat(),
                "technician": "Dallas Repair Crew B",
                "notes": "Warranty visit for drain and overflow alignment.",
            },
            {
                "job_number": "DAL-SVC-41039",
                "title": "Service silicone touch-up",
                "job_type": "Service",
                "customer_name": "Bryce Nelson",
                "address": "228 Fairfield Ridge Rd, Dallas, TX",
                "scheduled_for": (now + timedelta(days=7)).date().isoformat(),
                "technician": "Dallas Repair Crew B",
                "notes": "Bring sealant and trim clips for follow-up punch list.",
            },
            {
                "job_number": "DAL-WAR-41042",
                "title": "Warranty shower head swap",
                "job_type": "Warranty",
                "customer_name": "Angela Chen",
                "address": "1045 Stonegate Park, Dallas, TX",
                "scheduled_for": (now + timedelta(days=8)).date().isoformat(),
                "technician": "Dallas Repair Crew B",
                "notes": "Customer warranty ticket for hardware replacement.",
            },
        ],
        "CHI": [
            {
                "job_number": "CHI-52018",
                "title": "Tub-to-shower conversion",
                "job_type": "Install",
                "customer_name": "Alicia Harper",
                "address": "4110 W Addison St, Chicago, IL",
                "scheduled_for": (now + timedelta(days=1)).date().isoformat(),
                "technician": "Chicago Install Crew A",
                "notes": "Need wall panels and valve trim pulled together.",
            },
            {
                "job_number": "CHI-52021",
                "title": "Guest bath conversion install",
                "job_type": "Install",
                "customer_name": "Priya Singh",
                "address": "6430 N Artesian Ave, Chicago, IL",
                "scheduled_for": (now + timedelta(days=4)).date().isoformat(),
                "technician": "Chicago Install Crew A",
                "notes": "Need wall panel hardware and trim staged together.",
            },
            {
                "job_number": "CHI-SVC-52024",
                "title": "Bathroom repair follow-up",
                "job_type": "Service",
                "customer_name": "Martin Kehoe",
                "address": "820 S Maple Ave, Chicago, IL",
                "scheduled_for": (now + timedelta(days=3)).date().isoformat(),
                "technician": "Chicago Service Crew B",
                "notes": "Fast turnaround service call with seal and drain parts.",
            },
            {
                "job_number": "CHI-WAR-52028",
                "title": "Warranty trim adjustment",
                "job_type": "Warranty",
                "customer_name": "Harper Lowe",
                "address": "3128 W Cortland St, Chicago, IL",
                "scheduled_for": (now + timedelta(days=5)).date().isoformat(),
                "technician": "Chicago Service Crew B",
                "notes": "Warranty callback for escutcheon and handle fitment.",
            },
            {
                "job_number": "CHI-SVC-52032",
                "title": "Service faucet touch-up",
                "job_type": "Service",
                "customer_name": "Mason Bell",
                "address": "1209 S Oakley Blvd, Chicago, IL",
                "scheduled_for": (now + timedelta(days=6)).date().isoformat(),
                "technician": "Chicago Service Crew B",
                "notes": "Bring supply lines and faucet trim for service visit.",
            },
        ],
        "PHX": [
            {
                "job_number": "PHX-61012",
                "title": "Tub-to-shower conversion",
                "job_type": "Install",
                "customer_name": "Erica Stone",
                "address": "2741 E Cactus Bloom Trl, Phoenix, AZ",
                "scheduled_for": (now + timedelta(days=2)).date().isoformat(),
                "technician": "Phoenix Install Crew A",
                "notes": "Confirm valve body and hardware pack are staged.",
            },
            {
                "job_number": "PHX-SVC-61019",
                "title": "Bathroom repair follow-up",
                "job_type": "Service",
                "customer_name": "Luis Romero",
                "address": "5908 N Desert Harbor Dr, Phoenix, AZ",
                "scheduled_for": (now + timedelta(days=5)).date().isoformat(),
                "technician": "Phoenix Service Crew B",
                "notes": "Service visit for trim, drain, and silicone touch-up.",
            },
            {
                "job_number": "PHX-WAR-61022",
                "title": "Warranty wall panel inspection",
                "job_type": "Warranty",
                "customer_name": "Sierra Hodge",
                "address": "4029 E White Feather Ln, Phoenix, AZ",
                "scheduled_for": (now + timedelta(days=6)).date().isoformat(),
                "technician": "Phoenix Service Crew B",
                "notes": "Warranty inspection and likely trim replacement.",
            },
            {
                "job_number": "PHX-SVC-61025",
                "title": "Service drain reseal",
                "job_type": "Service",
                "customer_name": "Caleb Ortiz",
                "address": "1175 N Amber Creek Dr, Phoenix, AZ",
                "scheduled_for": (now + timedelta(days=7)).date().isoformat(),
                "technician": "Phoenix Service Crew B",
                "notes": "Bring drain kit, silicone, and misc install clips.",
            },
        ],
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
                    (warehouse_id, po_number, vendor_id, part_id, quantity, received_quantity, eta, notes, status, created_by_user_id, updated_by_user_id, updated_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    actor_user_id,
                    actor_user_id,
                    (now - timedelta(days=created_offsets[po_index - 1])).isoformat(),
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
                INSERT INTO receiving_logs (po_id, part_id, quantity, received_by, notes, created_at, checked_in_by_user_id, checked_in_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    received_po_id,
                    received_part_id,
                    received_quantity,
                    "Demo Receiver",
                    "Counted and shelved into the supply cage",
                    (now - timedelta(days=1)).isoformat(),
                    actor_user_id,
                    (now - timedelta(days=1)).isoformat(),
                ),
            )

        active_jobs = demo_jobs[warehouse_code]
        for job_index, job in enumerate(active_jobs):
            job_cursor = db.execute(
                """
                INSERT INTO jobs (
                    warehouse_id, job_number, title, customer_name, address, scheduled_for,
                    job_type, technician, assigned_user_id, status, notes, created_by_user_id, updated_by_user_id, updated_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    warehouse_id,
                    job["job_number"],
                    job["title"],
                    job["customer_name"],
                    job["address"],
                    job["scheduled_for"],
                    canonical_job_type(job.get("job_type"), job["title"]),
                    job["technician"],
                    user_map.get(job["technician"]),
                    "Active",
                    job["notes"],
                    actor_user_id,
                    actor_user_id,
                    (now - timedelta(hours=(job_index * 4) + 2)).isoformat(),
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
                        job["job_number"],
                        job["technician"],
                        part_id,
                        quantity,
                        "Active install allocation",
                        (now - timedelta(hours=(job_index * 4) + allocation_index)).isoformat(),
                    ),
                )

        for completed_index, job in enumerate(completed_demo_jobs[warehouse_code]):
            job_cursor = db.execute(
                """
                INSERT INTO jobs (
                    warehouse_id, job_number, title, customer_name, address, scheduled_for,
                    job_type, technician, assigned_user_id, status, notes, created_by_user_id, updated_by_user_id, completed_by_user_id, completed_at, updated_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Completed', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    warehouse_id,
                    job["job_number"],
                    job["title"],
                    job["customer_name"],
                    job["address"],
                    job["scheduled_for"],
                    canonical_job_type(job.get("job_type"), job["title"]),
                    job["technician"],
                    user_map.get(job["technician"]),
                    job["notes"],
                    actor_user_id,
                    actor_user_id,
                    actor_user_id,
                    (now - timedelta(days=job["days_ago"])).isoformat(),
                    (now - timedelta(days=job["days_ago"], hours=completed_index + 3)).isoformat(),
                    (now - timedelta(days=job["days_ago"], hours=completed_index + 3)).isoformat(),
                ),
            )
            completed_job_id = int(job_cursor.lastrowid)
            total_requirements = 4 if 'conversion' in job["title"].lower() else 3
            for allocation_index in range(total_requirements):
                part_key = part_keys[(warehouse_index * 19 + completed_index * 7 + allocation_index * 5 + 3) % len(part_keys)]
                required_quantity = 2 + ((allocation_index + completed_index + warehouse_index) % 3)
                if allocation_index == 0 and 'conversion' in job["title"].lower():
                    required_quantity += 2
                pulled_quantity = required_quantity
                part_id = part_map[part_key]
                db.execute(
                    """
                    INSERT INTO job_part_requirements (job_id, part_id, required_quantity, pulled_quantity, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        completed_job_id,
                        part_id,
                        required_quantity,
                        pulled_quantity,
                        (now - timedelta(days=job["days_ago"], hours=allocation_index + 1)).isoformat(),
                    ),
                )
                note = 'Completed job usage'
                if allocation_index == total_requirements - 1 and completed_index % 2 == 0:
                    note = 'Completed job extra material usage'
                db.execute(
                    """
                    INSERT INTO usage_logs (warehouse_id, job_number, technician, part_id, quantity, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        warehouse_id,
                        job["job_number"],
                        job["technician"],
                        part_id,
                        pulled_quantity,
                        note,
                        (now - timedelta(days=job["days_ago"], hours=allocation_index)).isoformat(),
                    ),
                )

        for history_index in range(24):
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
                    (now - timedelta(days=(history_index * 5) + 6, hours=warehouse_index + history_index)).isoformat(),
                ),
            )
    ensure_optional_columns(db)
    ensure_app_counters(db)
    db.commit()


def rows(query: str, params: tuple = ()) -> list[dict]:
    db = get_db()
    return [dict(row) for row in db.execute(query, params).fetchall()]


def selected_warehouse_id() -> int:
    db = get_db()
    requested = request.args.get("warehouseId") or (request.get_json(silent=True) or {}).get("warehouseId")
    if requested:
        return int(requested)
    user = current_user_record(db)
    if user is not None and str(user["role"]) not in GLOBAL_JOB_ACCESS_ROLES:
        assigned = db.execute(
            """
            SELECT warehouse_id
            FROM jobs
            WHERE assigned_user_id = ?
            ORDER BY CASE WHEN status = 'Completed' THEN 1 ELSE 0 END, datetime(created_at) DESC
            LIMIT 1
            """,
            (int(user["id"]),),
        ).fetchone()
        if assigned is not None:
            return int(assigned["warehouse_id"])
    return db.execute("SELECT id FROM warehouses WHERE is_active = 1 ORDER BY name LIMIT 1").fetchone()["id"]


def currentWarehouseIs(warehouse_id: int) -> bool:
    requested = request.args.get("warehouseId") or (request.get_json(silent=True) or {}).get("warehouseId")
    return bool(requested) and int(requested) == warehouse_id


def load_purchase_order_lines(db: sqlite3.Connection, po_ids: list[int]) -> dict[int, list[dict]]:
    if not po_ids:
        return {}
    placeholders = ",".join("?" for _ in po_ids)
    line_rows = [
        dict(row)
        for row in db.execute(
            f"""
            SELECT purchase_order_lines.*, parts.part_number, parts.description, parts.category, parts.item_type, parts.unit_cost
            FROM purchase_order_lines
            JOIN parts ON parts.id = purchase_order_lines.part_id
            WHERE purchase_order_lines.purchase_order_id IN ({placeholders})
            ORDER BY purchase_order_lines.purchase_order_id, parts.part_number
            """,
            tuple(po_ids),
        ).fetchall()
    ]
    grouped: dict[int, list[dict]] = {}
    for line in line_rows:
        grouped.setdefault(int(line["purchase_order_id"]), []).append(line)
    return grouped


def purchase_orders_for_warehouse(db: sqlite3.Connection, warehouse_id: int) -> list[dict]:
    purchase_orders = [
        dict(row)
        for row in db.execute(
            """
            SELECT purchase_orders.*, vendors.name AS vendor_name,
                   warehouses.name AS warehouse_name, warehouses.code AS warehouse_code,
                   created_by_user.display_name AS created_by_name,
                   updated_by_user.display_name AS updated_by_name,
                   (
                       SELECT checked_in_user.display_name
                       FROM receiving_logs
                       LEFT JOIN users AS checked_in_user ON checked_in_user.id = receiving_logs.checked_in_by_user_id
                       WHERE receiving_logs.po_id = purchase_orders.id
                       ORDER BY datetime(COALESCE(receiving_logs.checked_in_at, receiving_logs.created_at)) DESC
                       LIMIT 1
                   ) AS checked_in_by_name,
                   (
                       SELECT COALESCE(receiving_logs.checked_in_at, receiving_logs.created_at)
                       FROM receiving_logs
                       WHERE receiving_logs.po_id = purchase_orders.id
                       ORDER BY datetime(COALESCE(receiving_logs.checked_in_at, receiving_logs.created_at)) DESC
                       LIMIT 1
                   ) AS checked_in_at,
                   COALESCE(SUM(purchase_order_lines.quantity_ordered), 0) AS total_ordered,
                   COALESCE(SUM(purchase_order_lines.quantity_received), 0) AS total_received,
                   COUNT(purchase_order_lines.id) AS line_count
            FROM purchase_orders
            JOIN vendors ON vendors.id = purchase_orders.vendor_id
            JOIN warehouses ON warehouses.id = purchase_orders.warehouse_id
            LEFT JOIN purchase_order_lines ON purchase_order_lines.purchase_order_id = purchase_orders.id
            LEFT JOIN users AS created_by_user ON created_by_user.id = purchase_orders.created_by_user_id
            LEFT JOIN users AS updated_by_user ON updated_by_user.id = purchase_orders.updated_by_user_id
            WHERE purchase_orders.warehouse_id = ?
            GROUP BY purchase_orders.id
            ORDER BY datetime(purchase_orders.created_at) DESC
            """,
            (warehouse_id,),
        ).fetchall()
    ]
    line_map = load_purchase_order_lines(db, [int(po["id"]) for po in purchase_orders])
    for po in purchase_orders:
        lines = line_map.get(int(po["id"]), [])
        po["lines"] = lines
        po["total_ordered"] = int(po.get("total_ordered") or 0)
        po["total_received"] = int(po.get("total_received") or 0)
        po["outstanding_quantity"] = sum(max(int(line["quantity_ordered"]) - int(line["quantity_received"]), 0) for line in lines)
    return purchase_orders


def order_list_items_for_warehouse(db: sqlite3.Connection, warehouse_id: int) -> list[dict]:
    return [
        dict(row)
        for row in db.execute(
            """
            SELECT order_list_items.*, parts.part_number, parts.description, parts.category, parts.item_type, parts.stock,
                   vendors.name AS vendor_name, warehouses.code AS warehouse_code,
                   created_by_user.display_name AS created_by_name,
                   updated_by_user.display_name AS updated_by_name
            FROM order_list_items
            JOIN parts ON parts.id = order_list_items.part_id
            JOIN vendors ON vendors.id = order_list_items.vendor_id
            JOIN warehouses ON warehouses.id = order_list_items.warehouse_id
            LEFT JOIN users AS created_by_user ON created_by_user.id = order_list_items.created_by_user_id
            LEFT JOIN users AS updated_by_user ON updated_by_user.id = order_list_items.updated_by_user_id
            WHERE order_list_items.warehouse_id = ?
            ORDER BY datetime(order_list_items.created_at) DESC, parts.part_number
            """,
            (warehouse_id,),
        ).fetchall()
    ]


def bootstrap_payload(warehouse_id: int) -> dict:
    db = get_db()
    user = current_user_record(db)
    allowed_job_types = allowed_job_types_for_role(user["role"] if user is not None else None)
    has_global_job_access = bool(user and str(user["role"]) in GLOBAL_JOB_ACCESS_ROLES)
    job_params: tuple = (warehouse_id,) if has_global_job_access else (warehouse_id, int(user["id"]))
    job_filter = "" if has_global_job_access else " AND assigned_user_id = ?"
    current = safe_feature_load("selected warehouse", rows("SELECT * FROM warehouses WHERE id = ?", (warehouse_id,)), lambda: rows("SELECT * FROM warehouses WHERE id = ?", (warehouse_id,)))
    jobs = safe_feature_load(
        "jobs",
        [],
        lambda: rows(
            f"""
            SELECT jobs.*, users.display_name AS assigned_user_name, users.username AS assigned_username,
                   created_by_user.display_name AS created_by_name,
                   updated_by_user.display_name AS updated_by_name,
                   completed_by_user.display_name AS completed_by_name
            FROM jobs
            LEFT JOIN users ON users.id = jobs.assigned_user_id
            LEFT JOIN users AS created_by_user ON created_by_user.id = jobs.created_by_user_id
            LEFT JOIN users AS updated_by_user ON updated_by_user.id = jobs.updated_by_user_id
            LEFT JOIN users AS completed_by_user ON completed_by_user.id = jobs.completed_by_user_id
            WHERE jobs.warehouse_id = ? AND jobs.status != 'Completed'{job_filter}
            ORDER BY CASE WHEN jobs.status = 'Ready to Go' THEN 0 ELSE 1 END, datetime(jobs.created_at) DESC
            """,
            job_params,
        ),
    )
    for job in jobs:
        job["job_type"] = canonical_job_type(job.get("job_type"), job.get("title"))
    jobs = [job for job in jobs if job.get("job_type") in allowed_job_types]
    completed_jobs = safe_feature_load(
        "completed jobs",
        [],
        lambda: rows(
            f"""
            SELECT jobs.*, users.display_name AS assigned_user_name, users.username AS assigned_username,
                   created_by_user.display_name AS created_by_name,
                   updated_by_user.display_name AS updated_by_name,
                   completed_by_user.display_name AS completed_by_name
            FROM jobs
            LEFT JOIN users ON users.id = jobs.assigned_user_id
            LEFT JOIN users AS created_by_user ON created_by_user.id = jobs.created_by_user_id
            LEFT JOIN users AS updated_by_user ON updated_by_user.id = jobs.updated_by_user_id
            LEFT JOIN users AS completed_by_user ON completed_by_user.id = jobs.completed_by_user_id
            WHERE jobs.warehouse_id = ? AND jobs.status = 'Completed'{job_filter}
            ORDER BY datetime(jobs.created_at) DESC
            """,
            job_params,
        ),
    )
    for job in completed_jobs:
        job["job_type"] = canonical_job_type(job.get("job_type"), job.get("title"))
    completed_jobs = [job for job in completed_jobs if job.get("job_type") in allowed_job_types]
    visible_job_ids = {int(job["id"]) for job in jobs}
    visible_completed_job_ids = {int(job["id"]) for job in completed_jobs}
    visible_all_job_ids = visible_job_ids | visible_completed_job_ids
    job_requirements = safe_feature_load(
        "job requirements",
        [],
        lambda: rows(
            f"""
            SELECT job_part_requirements.*, parts.part_number, parts.description, parts.item_type
            FROM job_part_requirements
            JOIN jobs ON jobs.id = job_part_requirements.job_id
            JOIN parts ON parts.id = job_part_requirements.part_id
            WHERE jobs.warehouse_id = ?{job_filter}
            ORDER BY CASE WHEN jobs.status = 'Ready to Go' THEN 0 ELSE 1 END, jobs.created_at DESC, parts.part_number
            """,
            job_params,
        ),
    )
    job_requirements = [row for row in job_requirements if int(row["job_id"]) in visible_all_job_ids]
    visible_parts_query = (
        """
        SELECT parts.*, vendors.name AS vendor_name, warehouses.name AS warehouse_name, warehouses.code AS warehouse_code
        FROM parts
        JOIN vendors ON vendors.id = parts.vendor_id
        JOIN warehouses ON warehouses.id = parts.warehouse_id
        WHERE parts.warehouse_id = ?
        ORDER BY part_number
        """
        if bool(user and current_user_can("inventory_access", db))
        else """
        SELECT DISTINCT parts.*, vendors.name AS vendor_name, warehouses.name AS warehouse_name, warehouses.code AS warehouse_code
        FROM parts
        JOIN vendors ON vendors.id = parts.vendor_id
        JOIN warehouses ON warehouses.id = parts.warehouse_id
        JOIN job_part_requirements ON job_part_requirements.part_id = parts.id
        JOIN jobs ON jobs.id = job_part_requirements.job_id
        WHERE parts.warehouse_id = ? AND jobs.assigned_user_id = ?
        ORDER BY part_number
        """
    )
    visible_parts = safe_feature_load("parts", [], lambda: rows(visible_parts_query, job_params))
    job_attachments = safe_feature_load(
        "job attachments",
        [],
        lambda: rows(
            f"""
            SELECT job_attachments.*, users.display_name AS uploaded_by_name
            FROM job_attachments
            JOIN jobs ON jobs.id = job_attachments.job_id
            LEFT JOIN users ON users.id = job_attachments.uploaded_by_user_id
            WHERE jobs.warehouse_id = ?{job_filter}
            ORDER BY datetime(job_attachments.created_at) DESC
            """,
            job_params,
        ),
    )
    job_attachments = [row for row in job_attachments if int(row["job_id"]) in visible_all_job_ids]
    job_notes = safe_feature_load(
        "job notes",
        [],
        lambda: rows(
            f"""
            SELECT job_notes.*, users.display_name AS updated_by_name
            FROM job_notes
            JOIN jobs ON jobs.id = job_notes.job_id
            LEFT JOIN users ON users.id = job_notes.updated_by_user_id
            WHERE jobs.warehouse_id = ?{job_filter}
            ORDER BY datetime(job_notes.created_at) DESC
            """,
            job_params,
        ),
    )
    job_notes = [row for row in job_notes if int(row["job_id"]) in visible_all_job_ids]
    permissions = role_permissions(db, str(user["role"])) if user else {key: False for key in PERMISSION_KEYS}
    return {
        "currentUser": serialize_user(user),
        "users": safe_feature_load("users", [], lambda: all_users(db)) if current_user_can("user_management", db) else [],
        "rolePermissions": safe_feature_load("role permissions", [], lambda: all_role_permissions(db)) if current_user_can("user_management", db) else [],
        "currentUserPermissions": permissions,
        "featureFlags": FEATURE_FLAGS,
        "jobTypeOptions": list(JOB_TYPE_OPTIONS),
        "serviceFieldOptions": {
            "status": list(JOB_STATUS_OPTIONS),
            "serviceCode": list(SERVICE_CODE_OPTIONS),
            "probableIssueCategory": list(SERVICE_PROBABLE_ISSUE_OPTIONS),
            "serviceCategory": list(SERVICE_CATEGORY_OPTIONS),
            "urgency": list(SERVICE_URGENCY_OPTIONS),
            "paymentMethod": list(PAYMENT_METHOD_OPTIONS),
            "serviceFaultCategory": list(SERVICE_FAULT_CATEGORY_OPTIONS),
            "yesNo": list(YES_NO_OPTIONS),
            "detailDiscrepancyCategory": list(DETAIL_DISCREPANCY_CATEGORIES),
        },
        "warehouses": safe_feature_load("warehouses", [], lambda: rows("SELECT * FROM warehouses ORDER BY name")),
        "activeWarehouses": safe_feature_load("active warehouses", [], lambda: rows("SELECT * FROM warehouses WHERE is_active = 1 ORDER BY name")),
        "selectedWarehouseId": warehouse_id,
        "selectedWarehouse": current[0] if current else None,
        "emailSettings": {
            "sendAvailable": bool(smtp_settings()["enabled"]),
            "fromEmail": str(smtp_settings()["from_email"] or ""),
        },
        "vendors": safe_feature_load("vendors", [], lambda: rows("SELECT vendors.*, COALESCE(order_form_templates.name, '') AS linked_template_name FROM vendors LEFT JOIN order_form_templates ON order_form_templates.template_id = vendors.linked_template_id ORDER BY vendors.name")) if current_user_can("purchase_orders_access", db) else [],
        "orderFormTemplates": safe_feature_load("order forms", [], lambda: rows("SELECT * FROM order_form_templates ORDER BY name")) if current_user_can("purchase_orders_access", db) else [],
        "parts": visible_parts,
        "orderListItems": safe_feature_load("order list", [], lambda: order_list_items_for_warehouse(db, warehouse_id)) if current_user_can("purchase_orders_access", db) else [],
        "purchaseOrders": safe_feature_load("purchase orders", [], lambda: purchase_orders_for_warehouse(db, warehouse_id)) if current_user_can("purchase_orders_access", db) else [],
        "receivingLogs": safe_feature_load(
            "receiving logs",
            [],
            lambda: rows(
                """
                SELECT receiving_logs.*, purchase_orders.po_number, parts.part_number, purchase_orders.warehouse_id,
                       checked_in_user.display_name AS checked_in_by_name
                FROM receiving_logs
                LEFT JOIN purchase_orders ON purchase_orders.id = receiving_logs.po_id
                JOIN parts ON parts.id = receiving_logs.part_id
                LEFT JOIN users AS checked_in_user ON checked_in_user.id = receiving_logs.checked_in_by_user_id
                WHERE purchase_orders.warehouse_id = ?
                ORDER BY datetime(receiving_logs.created_at) DESC
                """,
                (warehouse_id,),
            ),
        ) if current_user_can("receiving_access", db) else [],
        "jobs": jobs,
        "completedJobs": completed_jobs,
        "jobRequirements": job_requirements,
        "jobAttachments": [serialize_job_attachment(row) for row in job_attachments],
        "jobNotes": job_notes,
        "usageLogs": safe_feature_load(
            "usage logs",
            [],
            lambda: rows(
                f"""
                SELECT usage_logs.*, parts.part_number, parts.description
                FROM usage_logs
                JOIN parts ON parts.id = usage_logs.part_id
                {"JOIN jobs ON jobs.job_number = usage_logs.job_number AND jobs.warehouse_id = usage_logs.warehouse_id" if not has_global_job_access else ""}
                WHERE usage_logs.warehouse_id = ?{" AND jobs.assigned_user_id = ?" if not has_global_job_access else ""}
                ORDER BY datetime(usage_logs.created_at) DESC
                """,
                job_params,
            ),
        ),
        "transferLogs": safe_feature_load(
            "transfer logs",
            [],
            lambda: rows(
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
        ) if current_user_can("edit_records", db) else [],
    }


def trim_insights_context(context: dict) -> dict:
    trimmed: dict[str, object] = {}
    for key, value in context.items():
        if isinstance(value, list):
            trimmed[key] = value[:80]
        elif isinstance(value, dict):
            trimmed[key] = {
                child_key: child_value[:40] if isinstance(child_value, list) else child_value
                for child_key, child_value in value.items()
            }
        else:
            trimmed[key] = value
    return trimmed


def extract_response_output_text(payload: dict) -> str:
    output_text = str(payload.get("output_text") or "").strip()
    if output_text:
        return output_text
    chunks: list[str] = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            text_value = content.get("text")
            if text_value:
                chunks.append(str(text_value))
    return "\n".join(chunk.strip() for chunk in chunks if chunk).strip()


def cleanup_json_text(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def safe_str_list(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def build_allowed_metric_map(context: dict) -> dict[str, dict]:
    metrics = context.get("metricsCatalog") or []
    if not isinstance(metrics, list):
        return {}
    allowed: dict[str, dict] = {}
    for metric in metrics:
        if isinstance(metric, dict) and str(metric.get("key") or "").strip():
            allowed[str(metric["key"]).strip()] = metric
    return allowed


def validate_scope_text(answer: str, selected_days: int) -> None:
    normalized = answer.lower()
    for days in (30, 60, 90, 180):
        phrase = f"last {days} days"
        if days != selected_days and phrase in normalized:
            raise RuntimeError("AI response referenced a date range outside the selected filter.")


def validate_percent_claims(answer: str, allowed_metrics: dict[str, dict]) -> None:
    import re

    allowed_percents = {
        str(metric.get("value")).rstrip("%")
        for metric in allowed_metrics.values()
        if isinstance(metric, dict) and isinstance(metric.get("value"), str) and str(metric.get("value")).endswith("%")
    }
    matches = re.findall(r"(\d+(?:\.\d+)?)%", answer)
    invalid = [match for match in matches if match not in allowed_percents]
    if invalid:
        raise RuntimeError("AI response included percentage claims that were not grounded in the provided metrics.")


def validate_ai_recommendations(response_obj: dict, context: dict) -> None:
    forecast_parts = {
        str(item.get("partNumber"))
        for item in (context.get("reorder") or [])
        if isinstance(item, dict) and (item.get("daysUntilReorder") is not None or int(item.get("stock") or 0) <= int(item.get("reorderPoint") or 0))
    }
    allowed_part_ids = {int(item) for item in context.get("allowedPartIds", []) if str(item).isdigit()}
    allowed_metrics = build_allowed_metric_map(context)
    selected_days = int(((context.get("scope") or {}).get("dateRangeDays") or 0) or 0)

    answer = str(response_obj.get("answer") or "").strip()
    if not answer:
        raise RuntimeError("AI response did not include an answer.")
    if selected_days:
        validate_scope_text(answer, selected_days)
    validate_percent_claims(answer, allowed_metrics)

    referenced_part_ids = [int(item) for item in response_obj.get("referenced_part_ids", []) if str(item).isdigit()]
    if any(part_id not in allowed_part_ids for part_id in referenced_part_ids):
        raise RuntimeError("AI response referenced part IDs that were not present in the provided context.")

    referenced_metrics = response_obj.get("referenced_metrics", [])
    if not isinstance(referenced_metrics, list):
        raise RuntimeError("AI response referenced metrics in an invalid format.")
    for metric in referenced_metrics:
        if not isinstance(metric, dict):
            raise RuntimeError("AI response referenced an invalid metric entry.")
        metric_key = str(metric.get("metric_key") or "").strip()
        if metric_key not in allowed_metrics:
            raise RuntimeError("AI response referenced a metric that was not present in the provided context.")

    recommended_actions = response_obj.get("recommended_actions", [])
    if not isinstance(recommended_actions, list):
        raise RuntimeError("AI response recommended actions in an invalid format.")
    for action in recommended_actions:
        if not isinstance(action, dict):
            raise RuntimeError("AI response included an invalid recommended action.")
        action_text = str(action.get("action") or "").lower()
        related_parts = safe_str_list(action.get("related_part_numbers"))
        supported_by = safe_str_list(action.get("supported_by"))
        if any(metric_key not in allowed_metrics for metric_key in supported_by):
            raise RuntimeError("AI response recommended an action using unsupported metrics.")
        if ("reorder" in action_text or "stock" in action_text or "order" in action_text) and related_parts:
            if any(part_number not in forecast_parts for part_number in related_parts):
                raise RuntimeError("AI response recommended reorder action unsupported by forecast data.")


def normalize_ai_response(response_obj: dict, context: dict, mode: str) -> dict:
    if not isinstance(response_obj, dict):
        raise RuntimeError("AI response was not a valid structured object.")
    validate_ai_recommendations(response_obj, context)
    scope = context.get("scope") or {}
    confidence = str(response_obj.get("confidence") or "medium").strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    return {
        "answer": str(response_obj.get("answer") or "").strip(),
        "confidence": confidence,
        "data_gaps": safe_str_list(response_obj.get("data_gaps")),
        "referenced_metrics": [
            {
                "metric_key": str(metric.get("metric_key") or "").strip(),
                "label": str((build_allowed_metric_map(context).get(str(metric.get("metric_key") or "").strip()) or {}).get("label") or metric.get("metric_key") or "").strip(),
                "value": str((build_allowed_metric_map(context).get(str(metric.get("metric_key") or "").strip()) or {}).get("value") or "").strip(),
                "why_it_matters": str(metric.get("why_it_matters") or "").strip(),
            }
            for metric in response_obj.get("referenced_metrics", [])
            if isinstance(metric, dict) and str(metric.get("metric_key") or "").strip()
        ],
        "recommended_actions": [
            {
                "action": str(action.get("action") or "").strip(),
                "rationale": str(action.get("rationale") or "").strip(),
                "supported_by": safe_str_list(action.get("supported_by")),
                "related_part_numbers": safe_str_list(action.get("related_part_numbers")),
            }
            for action in response_obj.get("recommended_actions", [])
            if isinstance(action, dict) and str(action.get("action") or "").strip()
        ],
        "scope": {
            "mode": mode,
            "filters": scope.get("filters") or {},
            "dateRangeDays": int(scope.get("dateRangeDays") or 0),
            "jobsAnalyzed": int(scope.get("jobsAnalyzed") or 0),
            "usageLogsAnalyzed": int(scope.get("usageLogsAnalyzed") or 0),
            "sampling": scope.get("sampling") or {},
        },
        "grounded": True,
    }


def call_openai_insights(context: dict, question: str, mode: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY to enable AI Insights.")

    model = os.environ.get("OPENAI_INSIGHTS_MODEL", "").strip() or os.environ.get("OPENAI_MODEL", "").strip() or "gpt-5.4"
    safe_context = trim_insights_context(context)
    task = (
        "Write an AI briefing for the Insights page."
        if mode == "brief"
        else f"Answer this user question about the inventory data: {question}"
    )
    instructions = (
        "You are an analytics assistant for a warehouse and job-parts application. "
        "Use only the structured data provided to you. Do not invent facts, counts, dates, or entities. "
        "When the data is insufficient, say so clearly. "
        "Keep the response practical, readable, and actionable. "
        "Reference specific parts, job types, vendors, crews, or anomalies when relevant. "
        "Do not override deterministic numbers; interpret them."
    )
    input_text = (
        f"{task}\n\n"
        "Return a single valid JSON object with this exact shape:\n"
        "{\n"
        '  "answer": string,\n'
        '  "confidence": "low" | "medium" | "high",\n'
        '  "data_gaps": string[],\n'
        '  "referenced_metrics": [{"metric_key": string, "why_it_matters": string}],\n'
        '  "recommended_actions": [{"action": string, "rationale": string, "supported_by": string[], "related_part_numbers": string[]}],\n'
        '  "referenced_part_ids": number[]\n'
        "}\n"
        "Use only metric_key values from metricsCatalog.\n"
        "Only include related_part_numbers when those parts appear in the provided context.\n"
        "If data is insufficient, say so in answer/confidence/data_gaps instead of guessing.\n"
        "Do not include markdown fences or extra text.\n\n"
        f"Structured data context:\n{json.dumps(safe_context, indent=2)}"
    )
    response_body = {
        "model": model,
        "instructions": instructions,
        "input": input_text,
        "reasoning": {"effort": "minimal"},
        "max_output_tokens": 900,
    }
    request_data = json.dumps(response_body).encode("utf-8")
    http_request = urllib_request.Request(
        "https://api.openai.com/v1/responses",
        data=request_data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(http_request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        try:
            error_payload = json.loads(error_body)
            message = error_payload.get("error", {}).get("message") or "OpenAI request failed."
        except json.JSONDecodeError:
            message = error_body or "OpenAI request failed."
        raise RuntimeError(message) from exc
    except urllib_error.URLError as exc:
        raise RuntimeError("Could not reach the OpenAI API from this app environment.") from exc

    answer = cleanup_json_text(extract_response_output_text(payload))
    if not answer:
        raise RuntimeError("The AI service returned an empty response.")
    try:
        response_obj = json.loads(answer)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The AI service returned invalid structured output.") from exc
    normalized = normalize_ai_response(response_obj, safe_context, mode)
    return {
        "response": normalized,
        "model": model,
        "response_id": payload.get("id", ""),
    }


def validate_scan_code_uniqueness(db: sqlite3.Connection, warehouse_id: int, scan_code: str, part_id: int | None = None) -> None:
    if not scan_code:
        return
    existing = db.execute(
        "SELECT id FROM parts WHERE warehouse_id = ? AND scan_code = ?",
        (warehouse_id, scan_code),
    ).fetchone()
    if existing is None:
        return
    if part_id is not None and int(existing["id"]) == part_id:
        return
    raise sqlite3.IntegrityError("duplicate scan code")


def scanned_part_for_job(db: sqlite3.Connection, warehouse_id: int, scan_value: str) -> sqlite3.Row | None:
    normalized = normalize_scan_code(scan_value)
    if not normalized:
        return None
    return db.execute(
        """
        SELECT *
        FROM parts
        WHERE warehouse_id = ?
          AND (scan_code = ? OR UPPER(part_number) = ?)
        ORDER BY CASE WHEN scan_code = ? THEN 0 ELSE 1 END
        LIMIT 1
        """,
        (warehouse_id, normalized, normalized, normalized),
    ).fetchone()


def serialize_scanned_part(part: sqlite3.Row, requirement: sqlite3.Row | None = None) -> dict:
    required_quantity = int(requirement["required_quantity"]) if requirement else 0
    pulled_quantity = int(requirement["pulled_quantity"]) if requirement else 0
    return {
        "id": int(part["id"]),
        "partNumber": part["part_number"],
        "scanCode": part["scan_code"],
        "description": part["description"],
        "category": part["category"],
        "itemType": part["item_type"],
        "currentStock": int(part["stock"]),
        "vendorId": int(part["vendor_id"]) if part["vendor_id"] is not None else None,
        "assignedToJob": requirement is not None,
        "requirementId": int(requirement["id"]) if requirement else None,
        "quantityNeeded": required_quantity,
        "quantityPulled": pulled_quantity,
        "quantityRemaining": max(required_quantity - pulled_quantity, 0),
    }


def requirement_for_job_part(db: sqlite3.Connection, job_id: int, part_id: int) -> sqlite3.Row | None:
    return db.execute(
        """
        SELECT job_part_requirements.*, jobs.job_number, jobs.technician, jobs.warehouse_id, jobs.status, jobs.assigned_user_id,
               parts.stock, parts.part_number, parts.description, parts.scan_code, parts.item_type
        FROM job_part_requirements
        JOIN jobs ON jobs.id = job_part_requirements.job_id
        JOIN parts ON parts.id = job_part_requirements.part_id
        WHERE job_part_requirements.job_id = ? AND job_part_requirements.part_id = ?
        """,
        (job_id, part_id),
    ).fetchone()


def requirement_with_context(db: sqlite3.Connection, requirement_id: int) -> sqlite3.Row | None:
    return db.execute(
        """
        SELECT job_part_requirements.*, jobs.job_number, jobs.technician, jobs.warehouse_id, jobs.status, jobs.assigned_user_id,
               parts.stock, parts.part_number, parts.description, parts.scan_code, parts.item_type
        FROM job_part_requirements
        JOIN jobs ON jobs.id = job_part_requirements.job_id
        JOIN parts ON parts.id = job_part_requirements.part_id
        WHERE job_part_requirements.id = ?
        """,
        (requirement_id,),
    ).fetchone()


def log_job_usage(
    db: sqlite3.Connection,
    warehouse_id: int,
    job_number: str,
    technician: str,
    part_id: int,
    quantity: int,
    notes: str,
) -> None:
    actor_id = current_user_id(db)
    db.execute(
        """
        INSERT INTO usage_logs (warehouse_id, job_number, technician, part_id, quantity, notes, created_at, created_by_user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (warehouse_id, job_number, technician, part_id, quantity, notes, datetime.now().isoformat(), actor_id),
    )


def pull_requirement_quantity(
    db: sqlite3.Connection,
    requirement: sqlite3.Row,
    quantity: int,
    notes: str,
    allow_overpull: bool = False,
) -> None:
    fresh_requirement = requirement_with_context(db, int(requirement["id"]))
    if fresh_requirement is None:
        raise ValueError("Job requirement not found.")
    actor_id = current_user_id(db)
    timestamp = datetime.now().isoformat()
    remaining = int(fresh_requirement["required_quantity"]) - int(fresh_requirement["pulled_quantity"])
    if not allow_overpull and quantity > remaining:
        raise ValueError(f"Only {remaining} part(s) remain to be pulled for that job.")
    part_update = db.execute(
        "UPDATE parts SET stock = stock - ? WHERE id = ? AND stock >= ?",
        (quantity, int(fresh_requirement["part_id"]), quantity),
    )
    if part_update.rowcount != 1:
        raise ValueError("Not enough inventory on hand for that pull.")

    if allow_overpull:
        requirement_update = db.execute(
            "UPDATE job_part_requirements SET pulled_quantity = pulled_quantity + ?, updated_by_user_id = ?, updated_at = ? WHERE id = ?",
            (quantity, actor_id, timestamp, int(fresh_requirement["id"])),
        )
    else:
        requirement_update = db.execute(
            """
            UPDATE job_part_requirements
            SET pulled_quantity = pulled_quantity + ?, updated_by_user_id = ?, updated_at = ?
            WHERE id = ? AND (required_quantity - pulled_quantity) >= ?
            """,
            (quantity, actor_id, timestamp, int(fresh_requirement["id"]), quantity),
        )
    if requirement_update.rowcount != 1:
        db.execute("UPDATE parts SET stock = stock + ? WHERE id = ?", (quantity, int(fresh_requirement["part_id"])))
        updated_requirement = requirement_with_context(db, int(fresh_requirement["id"]))
        latest_remaining = 0
        if updated_requirement is not None:
            latest_remaining = int(updated_requirement["required_quantity"]) - int(updated_requirement["pulled_quantity"])
        raise ValueError(f"Only {latest_remaining} part(s) remain to be pulled for that job.")

    log_job_usage(
        db,
        int(fresh_requirement["warehouse_id"]),
        str(fresh_requirement["job_number"]),
        str(fresh_requirement["technician"]),
        int(fresh_requirement["part_id"]),
        quantity,
        notes,
    )
    db.execute("UPDATE jobs SET updated_by_user_id = ?, updated_at = ? WHERE id = ?", (actor_id, timestamp, int(fresh_requirement["job_id"])))
    refresh_job_status(db, int(fresh_requirement["job_id"]))


def receive_requirement_direct_to_job(
    db: sqlite3.Connection,
    requirement: sqlite3.Row,
    quantity: int,
    notes: str,
) -> None:
    actor_id = current_user_id(db)
    timestamp = datetime.now().isoformat()
    remaining = int(requirement["required_quantity"]) - int(requirement["pulled_quantity"])
    if quantity > remaining:
        raise ValueError(f"Only {remaining} part(s) remain to be received for that job.")

    db.execute(
        "UPDATE job_part_requirements SET pulled_quantity = pulled_quantity + ?, updated_by_user_id = ?, updated_at = ? WHERE id = ?",
        (quantity, actor_id, timestamp, int(requirement["id"])),
    )
    log_job_usage(
        db,
        int(requirement["warehouse_id"]),
        str(requirement["job_number"]),
        str(requirement["technician"]),
        int(requirement["part_id"]),
        quantity,
        notes,
    )
    db.execute("UPDATE jobs SET updated_by_user_id = ?, updated_at = ? WHERE id = ?", (actor_id, timestamp, int(requirement["job_id"])))
    refresh_job_status(db, int(requirement["job_id"]))


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
    template = template_record_for_id(db, data.get("linked_template_id") or template_id_for_vendor_name(data["vendor_name"]))
    data["template_name"] = template["name"] if template else f"{data['vendor_name']} Template"
    data["form_variant"] = template["form_variant"] if template else reorder_form_variant(data["vendor_name"])
    data["request_date"] = datetime.fromisoformat(data["created_at"]).strftime("%B %d, %Y")
    data["line_total"] = round(data["quantity"] * data["unit_cost"], 2)
    data["mock_form_name"] = data["template_name"]
    data["line_items"] = [{
        "part_number": data["part_number"],
        "description": data["description"],
        "category": data["category"],
        "quantity_ordered": data["quantity"],
        "unit_cost": data["unit_cost"],
        "line_total": data["line_total"],
    }]
    data["plain_text_order"] = build_plain_text_order(data)
    return data


def build_plain_text_order(order: dict) -> str:
    lines = order.get("line_items") or []
    if not lines and order.get("part_number"):
        lines = [{
            "part_number": order.get("part_number", ""),
            "description": order.get("description", ""),
            "category": order.get("category", ""),
            "quantity_ordered": order.get("quantity", 0),
        }]
    header = [
        f"Vendor: {order.get('vendor_name', '')}",
        f"Warehouse: {order.get('warehouse_name', '')} ({order.get('warehouse_code', '')})",
        f"Request Date: {order.get('request_date', '')}",
        f"Status: {order.get('status', '')}",
        "",
        "Line Items:",
    ]
    body = [
        f"- {line.get('part_number', '')} | {line.get('description', '')} | Qty {line.get('quantity_ordered', 0)}"
        for line in lines
    ]
    footer = [
        "",
        f"Reason: {order.get('reason') or 'Low stock reorder'}",
        f"Prepared from ShopFlow for warehouse {order.get('warehouse_code', '')}."
    ]
    return "\n".join(header + body + footer)


def purchase_order_form_context(po_id: int) -> dict | None:
    db = get_db()
    row = db.execute(
        """
        SELECT purchase_orders.*, vendors.name AS vendor_name, vendors.contact AS vendor_contact, vendors.phone AS vendor_phone,
               warehouses.name AS warehouse_name, warehouses.code AS warehouse_code
        FROM purchase_orders
        JOIN vendors ON vendors.id = purchase_orders.vendor_id
        JOIN warehouses ON warehouses.id = purchase_orders.warehouse_id
        WHERE purchase_orders.id = ?
        """,
        (po_id,),
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    lines = load_purchase_order_lines(db, [po_id]).get(po_id, [])
    for line in lines:
        line["line_total"] = round(float(line["unit_cost"]) * int(line["quantity_ordered"]), 2)
    data["line_items"] = lines
    template = template_record_for_id(db, data.get("template_id") or template_id_for_vendor_name(data["vendor_name"]))
    data["template_name"] = template["name"] if template else f"{data['vendor_name']} Template"
    data["form_variant"] = template["form_variant"] if template else reorder_form_variant(data["vendor_name"])
    data["request_date"] = datetime.fromisoformat(data["created_at"]).strftime("%B %d, %Y")
    data["mock_form_name"] = data["template_name"]
    data["grand_total"] = round(sum(line["line_total"] for line in lines), 2)
    data["reason"] = data.get("notes", "")
    data["plain_text_order"] = build_plain_text_order(data)
    return data


@app.get("/")
def index() -> str:
    return render_template("index.html", feedback_url=os.environ.get("NEXT_PUBLIC_FEEDBACK_URL", "").strip())


@app.get("/test-notes")
def test_notes() -> str:
    return render_template("test_notes.html", feedback_url=os.environ.get("NEXT_PUBLIC_FEEDBACK_URL", "").strip())


@app.get("/api/auth/session")
def auth_session():
    user = current_user_record()
    if user is None:
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True, "currentUser": serialize_user(user)})


@app.post("/api/auth/login")
def auth_login():
    payload = request.get_json(force=True)
    username = str(payload.get("username") or "").strip().lower()
    password = str(payload.get("password") or "")
    if not username or not password:
        return jsonify({"error": "Enter a username and password."}), 400
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE LOWER(username) = ?", (username,)).fetchone()
    if user is None or not bool(user["is_active"]) or not check_password_hash(str(user["password_hash"]), password):
        return jsonify({"error": "Invalid username or password."}), 401
    session["user_id"] = int(user["id"])
    g.current_user_row = user
    return jsonify({"currentUser": serialize_user(user)})


@app.post("/api/auth/logout")
def auth_logout():
    session.pop("user_id", None)
    g.current_user_row = None
    return jsonify({"ok": True})


@app.post("/api/client-errors")
def client_error_log():
    payload = request.get_json(silent=True) or {}
    app.logger.error(
        "Client error | message=%s | source=%s | context=%s | stack=%s",
        str(payload.get("message") or "Unknown client error"),
        str(payload.get("source") or "ui"),
        payload.get("context") or {},
        str(payload.get("stack") or ""),
    )
    return jsonify({"ok": True})


@app.errorhandler(Exception)
def global_exception_handler(error: Exception):
    if request.path.startswith("/api/"):
        return handle_api_exception(error, "global_api_handler")
    log_server_error(error, "page_request")
    return render_template("index.html"), 500


@app.get("/reorders/<int:reorder_id>/form")
def reorder_form(reorder_id: int):
    if not current_user_is_manager():
        return "Manager access required.", 403
    context = reorder_form_context(reorder_id)
    if context is None:
        return "Reorder form not found.", 404
    return render_template("order_form.html", reorder=context)


@app.get("/purchase-orders/<int:po_id>/form")
def purchase_order_form(po_id: int):
    if not current_user_is_manager():
        return "Manager access required.", 403
    context = purchase_order_form_context(po_id)
    if context is None:
        return "Purchase order form not found.", 404
    return render_template("order_form.html", reorder=context)


@app.get("/api/bootstrap")
def api_bootstrap():
    return jsonify(bootstrap_payload(selected_warehouse_id()))


@app.post("/api/insights/ask")
@permission_required("reporting_access")
def api_insights_ask():
    payload = request.get_json(force=True)
    context = payload.get("context") or {}
    mode = str(payload.get("mode") or "query").strip().lower()
    question = str(payload.get("question") or "").strip()
    if mode not in {"brief", "query"}:
        return jsonify({"error": "Unsupported AI Insights mode."}), 400
    if mode == "query" and not question:
        return jsonify({"error": "Ask a question before sending the request."}), 400
    if not isinstance(context, dict):
        return jsonify({"error": "Insights context payload is invalid."}), 400
    try:
        ai_result = call_openai_insights(context, question, mode)
    except RuntimeError as exc:
        status_code = 503 if "OPENAI_API_KEY" in str(exc) else 502
        return jsonify({"error": str(exc)}), status_code
    return jsonify(
        {
            "response": ai_result["response"],
            "model": ai_result["model"],
            "responseId": ai_result["response_id"],
            "grounded": True,
            "mode": mode,
        }
    )


@app.post("/api/vendors")
@permission_required("purchase_orders_access")
def save_vendor():
    payload = request.get_json(force=True)
    db = get_db()
    fields = (
        payload["name"].strip(),
        payload["contact"].strip(),
        payload["email"].strip(),
        payload["phone"].strip(),
        int(payload["leadTimeDays"]),
        (payload.get("linkedTemplateId") or "").strip(),
    )
    vendor_id = payload.get("id")
    if vendor_id:
        db.execute(
            """
            UPDATE vendors
            SET name = ?, contact = ?, email = ?, phone = ?, lead_time_days = ?, linked_template_id = ?
            WHERE id = ?
            """,
            (*fields, int(vendor_id)),
        )
    else:
        db.execute(
            "INSERT INTO vendors (name, contact, email, phone, lead_time_days, linked_template_id) VALUES (?, ?, ?, ?, ?, ?)",
            fields,
        )
    db.commit()
    return jsonify(bootstrap_payload(selected_warehouse_id()))


@app.post("/api/users")
@permission_required("user_management")
def save_user():
    payload = request.get_json(force=True)
    db = get_db()
    username = str(payload.get("username") or "").strip().lower()
    display_name = str(payload.get("displayName") or "").strip()
    role = str(payload.get("role") or "").strip()
    password = str(payload.get("password") or "")
    is_active = 1 if bool(payload.get("isActive", True)) else 0
    if role not in DEFAULT_ROLE_PERMISSIONS:
        return jsonify({"error": "Choose a valid role."}), 400
    if not username or not display_name:
        return jsonify({"error": "Username and display name are required."}), 400
    user_id = payload.get("id")
    try:
        if user_id:
            existing = db.execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()
            if existing is None:
                return jsonify({"error": "User not found."}), 404
            if password:
                db.execute(
                    """
                    UPDATE users
                    SET username = ?, display_name = ?, role = ?, is_active = ?, password_hash = ?
                    WHERE id = ?
                    """,
                    (username, display_name, role, is_active, generate_password_hash(password), int(user_id)),
                )
            else:
                db.execute(
                    """
                    UPDATE users
                    SET username = ?, display_name = ?, role = ?, is_active = ?
                    WHERE id = ?
                    """,
                    (username, display_name, role, is_active, int(user_id)),
                )
        else:
            if not password:
                return jsonify({"error": "Set a password for the new user."}), 400
            db.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (username, generate_password_hash(password), display_name, role, is_active, datetime.now().isoformat()),
            )
    except sqlite3.IntegrityError:
        return jsonify({"error": "That username is already in use."}), 400
    db.commit()
    return jsonify(bootstrap_payload(selected_warehouse_id()))


@app.post("/api/role-permissions/<role>")
@permission_required("user_management")
def save_role_permission(role: str):
    if role not in DEFAULT_ROLE_PERMISSIONS:
        return jsonify({"error": "Unknown role."}), 404
    payload = request.get_json(force=True)
    values = {key: 1 if bool(payload.get(key, False)) else 0 for key in PERMISSION_KEYS}
    db = get_db()
    db.execute(
        """
        INSERT INTO role_permissions (
            role, inventory_access, job_access, purchase_orders_access, receiving_access, notes_access,
            user_management, reporting_access, receive_jobs, complete_jobs, edit_records, delete_records
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(role) DO UPDATE SET
            inventory_access = excluded.inventory_access,
            job_access = excluded.job_access,
            purchase_orders_access = excluded.purchase_orders_access,
            receiving_access = excluded.receiving_access,
            notes_access = excluded.notes_access,
            user_management = excluded.user_management,
            reporting_access = excluded.reporting_access,
            receive_jobs = excluded.receive_jobs,
            complete_jobs = excluded.complete_jobs,
            edit_records = excluded.edit_records,
            delete_records = excluded.delete_records
        """,
        (
            role,
            int(values["inventory_access"]),
            int(values["job_access"]),
            int(values["purchase_orders_access"]),
            int(values["receiving_access"]),
            int(values["notes_access"]),
            int(values["user_management"]),
            int(values["reporting_access"]),
            int(values["receive_jobs"]),
            int(values["complete_jobs"]),
            int(values["edit_records"]),
            int(values["delete_records"]),
        ),
    )
    db.commit()
    return jsonify(bootstrap_payload(selected_warehouse_id()))


@app.post("/api/order-form-templates")
@permission_required("purchase_orders_access")
def save_order_form_template():
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    fields = (
        payload["templateId"].strip(),
        payload["name"].strip(),
        payload.get("formVariant", "bathbuild").strip() or "bathbuild",
        payload.get("notes", "").strip(),
    )
    template_row_id = payload.get("id")
    timestamp = datetime.now().isoformat()
    try:
        if template_row_id:
            db.execute(
                """
                UPDATE order_form_templates
                SET template_id = ?, name = ?, form_variant = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (*fields, timestamp, int(template_row_id)),
            )
        else:
            db.execute(
                """
                INSERT INTO order_form_templates (template_id, name, form_variant, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (*fields, timestamp, timestamp),
            )
    except sqlite3.IntegrityError:
        return jsonify({"error": "That order form ID already exists."}), 400
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/order-form-templates/<int:template_row_id>/delete")
@permission_required("delete_records")
def delete_order_form_template(template_row_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    template = db.execute("SELECT * FROM order_form_templates WHERE id = ?", (template_row_id,)).fetchone()
    if template is None:
        return jsonify({"error": "Order form template not found."}), 404
    template_id = template["template_id"]
    vendor_count = db.execute("SELECT COUNT(*) AS count FROM vendors WHERE linked_template_id = ?", (template_id,)).fetchone()["count"]
    po_count = db.execute("SELECT COUNT(*) AS count FROM purchase_orders WHERE template_id = ?", (template_id,)).fetchone()["count"]
    order_list_count = db.execute("SELECT COUNT(*) AS count FROM order_list_items WHERE template_id = ?", (template_id,)).fetchone()["count"]
    if vendor_count or po_count or order_list_count:
        return jsonify({"error": "This order form is in use and cannot be deleted."}), 400
    db.execute("DELETE FROM order_form_templates WHERE id = ?", (template_row_id,))
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/vendors/<int:vendor_id>/delete")
@permission_required("delete_records")
def delete_vendor(vendor_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    part_count = db.execute("SELECT COUNT(*) AS count FROM parts WHERE vendor_id = ?", (vendor_id,)).fetchone()["count"]
    po_count = db.execute("SELECT COUNT(*) AS count FROM purchase_orders WHERE vendor_id = ?", (vendor_id,)).fetchone()["count"]
    order_list_count = db.execute("SELECT COUNT(*) AS count FROM order_list_items WHERE vendor_id = ?", (vendor_id,)).fetchone()["count"]
    if part_count or po_count or order_list_count:
        return jsonify({"error": "This vendor is in use and cannot be deleted."}), 400

    db.execute("DELETE FROM vendors WHERE id = ?", (vendor_id,))
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/warehouses")
@permission_required("edit_records")
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
@permission_required("edit_records")
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
@permission_required("inventory_access")
def save_part():
    payload = request.get_json(force=True)
    db = get_db()
    stock = int(payload["stock"])
    reorder_point = int(payload["reorderPoint"])
    unit_cost = float(payload["unitCost"])
    item_type = (payload.get("itemType") or "stocked").strip().lower()
    if stock < 0:
        return jsonify({"error": "Current stock cannot be negative."}), 400
    if reorder_point < 0:
        return jsonify({"error": "Reorder point cannot be negative."}), 400
    if unit_cost < 0:
        return jsonify({"error": "Unit cost cannot be negative."}), 400
    if item_type not in {"stocked", "non_stock"}:
        return jsonify({"error": "Item type must be Stocked or Non-Stock."}), 400

    part_number = payload["partNumber"].strip()
    scan_code = normalize_scan_code(payload.get("scanCode") or part_number)
    fields = (
        int(payload["warehouseId"]),
        part_number,
        scan_code,
        payload["description"].strip(),
        payload["category"].strip(),
        item_type,
        stock,
        reorder_point,
        int(payload["vendorId"]),
        unit_cost,
    )
    part_id = payload.get("id")
    actor_id = current_user_id(db)
    timestamp = datetime.now().isoformat()
    try:
        validate_scan_code_uniqueness(db, int(payload["warehouseId"]), scan_code, int(part_id) if part_id else None)
        if part_id:
            db.execute(
                """
                UPDATE parts
                SET warehouse_id = ?, part_number = ?, scan_code = ?, description = ?, category = ?, item_type = ?, stock = ?, reorder_point = ?, vendor_id = ?, unit_cost = ?, updated_by_user_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (*fields, actor_id, timestamp, int(part_id)),
            )
        else:
            db.execute(
                """
                INSERT INTO parts
                    (warehouse_id, part_number, scan_code, description, category, item_type, stock, reorder_point, vendor_id, unit_cost, created_by_user_id, updated_by_user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*fields, actor_id, actor_id, timestamp, timestamp),
            )
    except sqlite3.IntegrityError:
        return jsonify({"error": "That part number or scan code already exists in this warehouse."}), 400
    db.commit()
    return jsonify(bootstrap_payload(int(payload["warehouseId"])))


@app.post("/api/parts/<int:part_id>/delete")
@permission_required("delete_records")
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
@permission_required("purchase_orders_access")
def create_purchase_order():
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    vendor_id = int(payload["vendorId"])
    part_id = int(payload["partId"])
    quantity = int(payload["quantity"])
    if quantity <= 0:
        return jsonify({"error": "Quantity must be at least 1."}), 400

    db = get_db()
    timestamp = datetime.now().isoformat()
    actor_id = current_user_id(db)
    try:
        begin_immediate_transaction(db)
        po_number = next_po_number(db)
        po_cursor = db.execute(
            """
            INSERT INTO purchase_orders
                (warehouse_id, po_number, vendor_id, template_id, eta, notes, status, created_at, updated_at, part_id, quantity, received_quantity, created_by_user_id, updated_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, 'Email Pending', ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                warehouse_id,
                po_number,
                vendor_id,
                template_id_for_vendor_id(db, vendor_id),
                payload.get("eta", ""),
                payload.get("notes", "").strip(),
                timestamp,
                timestamp,
                part_id,
                quantity,
                actor_id,
                actor_id,
            ),
        )
        po_id = int(po_cursor.lastrowid)
        db.execute(
            """
            INSERT INTO purchase_order_lines (
                purchase_order_id, part_id, quantity_ordered, quantity_received, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, 0, ?, ?, ?)
            """,
            (po_id, part_id, quantity, payload.get("notes", "").strip(), timestamp, timestamp),
        )
        sync_purchase_order_rollups(db, po_id)
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({"error": "Another purchase order was created at the same time. Please try again."}), 409
    db.commit()
    return jsonify({"state": bootstrap_payload(warehouse_id), "createdPoId": po_id})


@app.post("/api/order-list")
@permission_required("purchase_orders_access")
def add_to_order_list():
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    part_id = int(payload["partId"])
    quantity = int(payload["quantity"])
    notes = payload.get("notes", "").strip()
    if quantity <= 0:
        return jsonify({"error": "Quantity must be at least 1."}), 400

    db = get_db()
    part = db.execute(
        """
        SELECT parts.*, vendors.name AS vendor_name
        FROM parts
        JOIN vendors ON vendors.id = parts.vendor_id
        WHERE parts.id = ? AND parts.warehouse_id = ?
        """,
        (part_id, warehouse_id),
    ).fetchone()
    if part is None:
        return jsonify({"error": "Part not found in this warehouse."}), 404

    existing = db.execute(
        "SELECT * FROM order_list_items WHERE warehouse_id = ? AND part_id = ?",
        (warehouse_id, part_id),
    ).fetchone()
    timestamp = datetime.now().isoformat()
    actor_id = current_user_id(db)
    template_id = template_id_for_vendor_name(part["vendor_name"])
    if existing:
        db.execute(
            """
            UPDATE order_list_items
            SET quantity_requested = ?, notes = ?, vendor_id = ?, template_id = ?, updated_at = ?, updated_by_user_id = ?
            WHERE id = ?
            """,
            (quantity, notes or existing["notes"], int(part["vendor_id"]), template_id, timestamp, actor_id, int(existing["id"])),
        )
    else:
        db.execute(
            """
            INSERT INTO order_list_items (
                warehouse_id, part_id, vendor_id, template_id, quantity_requested, notes, created_at, updated_at, created_by_user_id, updated_by_user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (warehouse_id, part_id, int(part["vendor_id"]), template_id, quantity, notes, timestamp, timestamp, actor_id, actor_id),
        )
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/order-list/<int:item_id>")
@permission_required("purchase_orders_access")
def update_order_list_item(item_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    quantity = int(payload["quantity"])
    if quantity <= 0:
        return jsonify({"error": "Quantity must be at least 1."}), 400
    db = get_db()
    db.execute(
        "UPDATE order_list_items SET quantity_requested = ?, notes = ?, updated_at = ?, updated_by_user_id = ? WHERE id = ? AND warehouse_id = ?",
        (quantity, payload.get("notes", "").strip(), datetime.now().isoformat(), current_user_id(db), item_id, warehouse_id),
    )
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/order-list/<int:item_id>/delete")
@permission_required("delete_records")
def delete_order_list_item(item_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    db.execute("DELETE FROM order_list_items WHERE id = ? AND warehouse_id = ?", (item_id, warehouse_id))
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/order-list/clear")
@permission_required("purchase_orders_access")
def clear_order_list():
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    db.execute("DELETE FROM order_list_items WHERE warehouse_id = ?", (warehouse_id,))
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/order-list/generate")
@permission_required("purchase_orders_access")
def generate_grouped_purchase_orders():
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    items = db.execute(
        """
        SELECT order_list_items.*, parts.part_number, parts.description, vendors.name AS vendor_name
        FROM order_list_items
        JOIN parts ON parts.id = order_list_items.part_id
        JOIN vendors ON vendors.id = order_list_items.vendor_id
        WHERE order_list_items.warehouse_id = ?
        ORDER BY order_list_items.vendor_id, order_list_items.template_id, order_list_items.id
        """,
        (warehouse_id,),
    ).fetchall()
    if not items:
        return jsonify({"error": "Add parts to the order list before generating orders."}), 400

    grouped = {}
    for item in items:
        key = (int(item["vendor_id"]), item["template_id"] or "", int(item["warehouse_id"]))
        grouped.setdefault(key, []).append(item)

    timestamp = datetime.now().isoformat()
    created_summary = []
    actor_id = current_user_id(db)
    try:
        begin_immediate_transaction(db)
        for (vendor_id, template_id, item_warehouse_id), grouped_items in grouped.items():
            po_number = next_po_number(db)
            eta_value = (datetime.now() + timedelta(days=7)).date().isoformat()
            po_cursor = db.execute(
                """
                INSERT INTO purchase_orders
                    (warehouse_id, po_number, vendor_id, template_id, eta, notes, status, created_at, updated_at, part_id, quantity, received_quantity, created_by_user_id, updated_by_user_id)
                VALUES (?, ?, ?, ?, ?, ?, 'Email Pending', ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    item_warehouse_id,
                    po_number,
                    vendor_id,
                    template_id,
                    eta_value,
                    payload.get("notes", "").strip() or "Generated from grouped order list",
                    timestamp,
                    timestamp,
                    int(grouped_items[0]["part_id"]),
                    sum(int(item["quantity_requested"]) for item in grouped_items),
                    actor_id,
                    actor_id,
                ),
            )
            po_id = int(po_cursor.lastrowid)
            line_items = []
            for item in grouped_items:
                db.execute(
                    """
                    INSERT INTO purchase_order_lines (
                        purchase_order_id, part_id, quantity_ordered, quantity_received, notes, created_at, updated_at
                    )
                    VALUES (?, ?, ?, 0, ?, ?, ?)
                    """,
                    (po_id, int(item["part_id"]), int(item["quantity_requested"]), item["notes"] or "", timestamp, timestamp),
                )
                line_items.append({
                    "partNumber": item["part_number"],
                    "description": item["description"],
                    "quantityOrdered": int(item["quantity_requested"]),
                })
            sync_purchase_order_rollups(db, po_id)
            created_summary.append({
                "id": po_id,
                "poNumber": po_number,
                "vendorName": grouped_items[0]["vendor_name"],
                "lineItems": line_items,
            })
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({"error": "Another purchase-order batch was created at the same time. Please try again."}), 409

    db.execute("DELETE FROM order_list_items WHERE warehouse_id = ?", (warehouse_id,))
    db.commit()
    return jsonify({"state": bootstrap_payload(warehouse_id), "createdPurchaseOrders": created_summary})


@app.post("/api/purchase-orders/<int:po_id>/status")
@permission_required("purchase_orders_access")
def update_purchase_order_status(po_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    status = payload["status"].strip()
    allowed = {"Email Pending", "Waiting for Part", "Partial Received", "Received"}
    if status not in allowed:
        return jsonify({"error": "Invalid purchase order status."}), 400

    db = get_db()
    db.execute(
        "UPDATE purchase_orders SET status = ?, updated_at = ?, updated_by_user_id = ? WHERE id = ?",
        (status, datetime.now().isoformat(), current_user_id(db), po_id),
    )
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/purchase-orders/<int:po_id>/receive")
@permission_required("receiving_access")
def receive_purchase_order(po_id: int):
    payload = request.get_json(force=True)

    db = get_db()
    begin_immediate_transaction(db)
    po = db.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
    if po is None:
        db.rollback()
        return jsonify({"error": "Purchase order not found."}), 404

    lines = db.execute("SELECT * FROM purchase_order_lines WHERE purchase_order_id = ? ORDER BY id", (po_id,)).fetchall()
    if not lines:
        db.rollback()
        return jsonify({"error": "This purchase order has no line items."}), 400

    line_receipts = payload.get("lineReceipts") or {}
    line_verifications = payload.get("lineVerifications") or {}
    allow_overage = bool(payload.get("allowOverage"))
    if not isinstance(line_receipts, dict) or not isinstance(line_verifications, dict):
        db.rollback()
        return jsonify({"error": "Invalid receiving payload."}), 400

    receipt_rows = []
    for line in lines:
        line_id = int(line["id"])
        amount = int(line_receipts.get(str(line_id), line_receipts.get(line_id, 0)) or 0)
        verified = bool(line_verifications.get(str(line_id), line_verifications.get(line_id, False)))
        if amount < 0:
            db.rollback()
            return jsonify({"error": "Received quantities cannot be negative."}), 400
        outstanding = max(int(line["quantity_ordered"]) - int(line["quantity_received"]), 0)
        if amount > outstanding and not allow_overage:
            db.rollback()
            return jsonify({"error": f"Line {line_id} cannot receive more than the outstanding quantity without confirmation."}), 400
        if amount > 0 and not verified:
            db.rollback()
            return jsonify({"error": "Each line item must be visually verified before it can be received."}), 400
        if amount > 0:
            receipt_rows.append((line, amount))
    if not receipt_rows:
        db.rollback()
        return jsonify({"error": "Enter a received quantity greater than 0 for at least one verified line."}), 400

    timestamp = datetime.now().isoformat()
    actor_id = current_user_id(db)
    for line, amount in receipt_rows:
        db.execute("UPDATE parts SET stock = stock + ? WHERE id = ?", (amount, int(line["part_id"])))
        db.execute(
            "INSERT INTO receiving_logs (po_id, part_id, quantity, received_by, notes, created_at, checked_in_by_user_id, checked_in_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                po_id,
                int(line["part_id"]),
                amount,
                payload.get("receivedBy", "").strip() or "Inventory",
                payload.get("notes", "").strip() or "Checked in from PO tab",
                timestamp,
                actor_id,
                timestamp,
            ),
        )
        db.execute(
            "UPDATE purchase_order_lines SET quantity_received = quantity_received + ?, updated_at = ? WHERE id = ?",
            (amount, timestamp, int(line["id"])),
        )

    sync_purchase_order_rollups(db, po_id)
    summary = db.execute(
        """
        SELECT SUM(CASE WHEN quantity_received >= quantity_ordered THEN 1 ELSE 0 END) AS complete_lines,
               COUNT(*) AS total_lines
        FROM purchase_order_lines
        WHERE purchase_order_id = ?
        """,
        (po_id,),
    ).fetchone()
    status = "Received" if int(summary["complete_lines"] or 0) == int(summary["total_lines"] or 0) else "Partial Received"
    db.execute(
        "UPDATE purchase_orders SET status = ?, updated_at = ?, updated_by_user_id = ? WHERE id = ?",
        (status, timestamp, actor_id, po_id),
    )
    db.commit()
    return jsonify(bootstrap_payload(int(po["warehouse_id"])))


@app.post("/api/reorders")
@permission_required("purchase_orders_access")
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
@permission_required("purchase_orders_access")
def create_order_more_purchase_order():
    return add_to_order_list()


@app.post("/api/reorders/<int:reorder_id>/sent")
@permission_required("purchase_orders_access")
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

    timestamp = datetime.now().isoformat()
    vendor_id = int(reorder["vendor_id"] or reorder["part_vendor_id"])
    actor_id = current_user_id(db)
    try:
        begin_immediate_transaction(db)
        po_cursor = db.execute(
            """
            INSERT INTO purchase_orders
                (warehouse_id, po_number, vendor_id, template_id, eta, notes, status, created_at, updated_at, part_id, quantity, received_quantity, created_by_user_id, updated_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, 'Email Pending', ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                warehouse_id,
                next_po_number(db),
                vendor_id,
                template_id_for_vendor_id(db, vendor_id),
                (datetime.now() + timedelta(days=7)).date().isoformat(),
                reorder["reason"] or "Generated from reorder request",
                timestamp,
                timestamp,
                int(reorder["part_id"]),
                int(reorder["quantity"]),
                actor_id,
                actor_id,
            ),
        )
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({"error": "Another purchase order was created at the same time. Please try again."}), 409
    po_id = int(po_cursor.lastrowid)
    db.execute(
        """
        INSERT INTO purchase_order_lines (
            purchase_order_id, part_id, quantity_ordered, quantity_received, notes, created_at, updated_at
        )
        VALUES (?, ?, ?, 0, ?, ?, ?)
        """,
        (po_id, int(reorder["part_id"]), int(reorder["quantity"]), reorder["reason"] or "", timestamp, timestamp),
    )
    sync_purchase_order_rollups(db, po_id)
    db.execute("UPDATE reorder_requests SET status = 'Sent to PO' WHERE id = ?", (reorder_id,))
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/receiving")
@permission_required("receiving_access")
def receive_parts():
    payload = request.get_json(force=True)
    po_id = int(payload["poId"])
    line_receipts = payload.get("lineReceipts")
    if not line_receipts:
        quantity = int(payload.get("quantity") or 0)
        db = get_db()
        first_line = db.execute("SELECT id FROM purchase_order_lines WHERE purchase_order_id = ? ORDER BY id LIMIT 1", (po_id,)).fetchone()
        if first_line is None:
            return jsonify({"error": "Purchase order not found."}), 404
        payload["lineReceipts"] = {str(first_line["id"]): quantity}
    payload.setdefault("receivedBy", payload.get("receivedBy", "Inventory"))
    payload.setdefault("lineVerifications", {str(line_id): True for line_id in payload["lineReceipts"]})
    return receive_purchase_order(po_id)


@app.post("/api/usage")
@permission_required("edit_records")
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
        INSERT INTO usage_logs (warehouse_id, job_number, technician, part_id, quantity, notes, created_at, created_by_user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(payload["warehouseId"]),
            payload["jobNumber"].strip(),
            payload["technician"].strip(),
            part["id"],
            quantity,
            payload.get("notes", "").strip(),
            datetime.now().isoformat(),
            current_user_id(db),
        ),
    )
    db.commit()
    return jsonify(bootstrap_payload(int(payload["warehouseId"])))


@app.post("/api/jobs")
@permission_required("job_access")
def create_job():
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    assigned_user_id = int(payload["assignedUserId"]) if payload.get("assignedUserId") else None
    db = get_db()
    assigned_user = require_assignable_user(db, assigned_user_id)
    if assigned_user_id and assigned_user is None:
        return jsonify({"error": "Assign the job to an active installer or service tech."}), 400
    requirements = payload.get("requirements", [])
    valid_requirements = []
    for requirement in requirements:
        part_id = int(requirement["partId"])
        required_quantity = int(requirement["requiredQuantity"])
        if required_quantity <= 0:
            continue
        part = db.execute(
            "SELECT id FROM parts WHERE id = ? AND warehouse_id = ?",
            (part_id, warehouse_id),
        ).fetchone()
        if part is None:
            return jsonify({"error": "One of the selected parts is not in this warehouse."}), 400
        valid_requirements.append((part_id, required_quantity))

    job_number = payload.get("jobNumber", "").strip()
    title = payload.get("title", "").strip()
    customer_name = payload.get("customerName", "").strip()
    address = payload.get("address", "").strip()
    scheduled_for = payload.get("scheduledFor", "").strip()
    job_type = payload.get("jobType", "").strip()
    if not job_number or not title or not customer_name or not address or not scheduled_for:
        return jsonify({"error": "Job number, customer, address, title, and scheduled date are required."}), 400
    if job_type not in JOB_TYPE_OPTIONS:
        return jsonify({"error": "Choose a valid job type."}), 400
    service_job = is_service_job_type(job_type)
    detail_job = is_detail_job_type(job_type)
    actor_id = current_user_id(db)
    timestamp = datetime.now().isoformat()
    technician_name = payload.get("technician", "").strip() or (assigned_user["display_name"] if assigned_user else "")
    service_fields = normalize_service_job_payload(payload)
    if service_job:
        related_install = related_install_context(
            db,
            warehouse_id,
            contract_number=str(service_fields["contract_number"]),
            customer_name=customer_name,
            address=address,
        )
        if related_install is not None:
            service_fields["sale_date"] = str(service_fields["sale_date"] or related_install["sale_date"] or "")
            service_fields["salesperson"] = str(service_fields["salesperson"] or related_install["salesperson"] or "")
            service_fields["install_date"] = str(service_fields["install_date"] or related_install["scheduled_for"] or related_install["install_date"] or "")
            service_fields["product_type"] = str(service_fields["product_type"] or related_install["product_type"] or "")
            service_fields["color"] = str(service_fields["color"] or related_install["color"] or "")
            service_fields["contract_number"] = str(service_fields["contract_number"] or related_install["contract_number"] or "")
            service_fields["primary_phone"] = str(service_fields["primary_phone"] or related_install["primary_phone"] or "")
            service_fields["secondary_phone"] = str(service_fields["secondary_phone"] or related_install["secondary_phone"] or "")
            service_fields["email"] = str(service_fields["email"] or related_install["email"] or "")
        service_fields["customer_name_primary"] = str(service_fields["customer_name_primary"] or customer_name)
        service_fields["address_line_1"] = str(service_fields["address_line_1"] or address)
        service_fields["prior_visit_count"] = prior_service_visit_count(
            db,
            warehouse_id,
            contract_number=str(service_fields["contract_number"]),
            customer_name=str(service_fields["customer_name_primary"]),
            address=str(service_fields["address_line_1"]),
        )
        validation_error = validate_service_job_fields(service_fields)
        if validation_error:
            return jsonify({"error": validation_error}), 400
    else:
        service_fields = normalize_service_job_payload({})
    status_value = str(service_fields["service_status"] if service_job else "Active")

    try:
        cursor = db.execute(
            """
            INSERT INTO jobs (
                warehouse_id, job_number, title, customer_name, address, scheduled_for,
                job_type, technician, assigned_user_id, status, notes,
                service_code, office_number, zone_number, contract_number, call_date, scheduled_time,
                estimated_hours, prior_visit_count, customer_name_primary, customer_name_secondary, address_line_1,
                city, state, zip, primary_phone, secondary_phone, email, best_contact_note, sale_date, salesperson,
                install_date, product_type, color, customer_complaint, dispatch_description, probable_issue_category,
                service_category, urgency, internal_notes, return_trip_required, return_reason, return_estimated_hours,
                survey_left, parts_to_order, service_cost, payment_method, no_payment_due, start_time, end_time,
                travel_time_minutes, total_time_minutes, customer_comments, customer_signature, paid_service,
                service_fault_category, service_item, service_issue, manager_approval_name, manager_approval_date,
                return_for_credit, service_record_id,
                created_by_user_id, updated_by_user_id, updated_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                warehouse_id,
                job_number,
                title,
                customer_name,
                address,
                scheduled_for,
                job_type,
                technician_name or "Unassigned",
                int(assigned_user["id"]) if assigned_user is not None else None,
                status_value,
                payload.get("notes", "").strip(),
                service_fields["service_code"],
                service_fields["office_number"],
                service_fields["zone_number"],
                service_fields["contract_number"],
                service_fields["call_date"],
                service_fields["scheduled_time"],
                service_fields["estimated_hours"],
                int(service_fields["prior_visit_count"]),
                service_fields["customer_name_primary"],
                service_fields["customer_name_secondary"],
                service_fields["address_line_1"],
                service_fields["city"],
                service_fields["state"],
                service_fields["zip"],
                service_fields["primary_phone"],
                service_fields["secondary_phone"],
                service_fields["email"],
                service_fields["best_contact_note"],
                service_fields["sale_date"],
                service_fields["salesperson"],
                service_fields["install_date"],
                service_fields["product_type"],
                service_fields["color"],
                service_fields["customer_complaint"],
                service_fields["dispatch_description"],
                service_fields["probable_issue_category"],
                service_fields["service_category"],
                service_fields["urgency"],
                service_fields["internal_notes"],
                service_fields["return_trip_required"],
                service_fields["return_reason"],
                service_fields["return_estimated_hours"],
                service_fields["survey_left"],
                service_fields["parts_to_order"],
                service_fields["service_cost"],
                service_fields["payment_method"],
                service_fields["no_payment_due"],
                service_fields["start_time"],
                service_fields["end_time"],
                int(service_fields["travel_time_minutes"]),
                int(service_fields["total_time_minutes"]),
                service_fields["customer_comments"],
                service_fields["customer_signature"],
                service_fields["paid_service"],
                service_fields["service_fault_category"],
                service_fields["service_item"],
                service_fields["service_issue"],
                service_fields["manager_approval_name"],
                service_fields["manager_approval_date"],
                service_fields["return_for_credit"],
                service_fields["service_record_id"],
                actor_id,
                actor_id,
                timestamp,
                timestamp,
            ),
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "That job could not be created. Check the job number and assignee, then try again."}), 400
    job_id = int(cursor.lastrowid)
    if detail_job:
        detail_fields = normalize_detail_job_payload(payload)
        detail_fields["linked_contract_number"] = str(
            detail_fields["linked_contract_number"] or payload.get("contract_number", "") or job_number
        )
        apply_detail_job_fields(db, job_id, detail_fields, actor_id)
    for part_id, required_quantity in valid_requirements:
        db.execute(
            """
            INSERT INTO job_part_requirements (
                job_id, part_id, required_quantity, pulled_quantity, created_by_user_id, updated_by_user_id, updated_at, created_at
            )
            VALUES (?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (job_id, part_id, required_quantity, actor_id, actor_id, timestamp, timestamp),
        )
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/jobs/<int:job_id>")
@permission_required("edit_records")
def update_job(job_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id = ? AND warehouse_id = ?", (job_id, warehouse_id)).fetchone()
    if job is None:
        return jsonify({"error": "Job not found."}), 404
    assigned_user_id = int(payload["assignedUserId"]) if payload.get("assignedUserId") else None
    assigned_user = require_assignable_user(db, assigned_user_id)
    if assigned_user_id and assigned_user is None:
        return jsonify({"error": "Assign the job to an active installer or service tech."}), 400

    requirement_quantities = payload.get("requirementQuantities") or []
    validated_requirements: list[tuple[int, int, int]] = []
    for item in requirement_quantities:
        requirement_id = int(item["requirementId"])
        required_quantity = int(item["requiredQuantity"])
        requirement = db.execute(
            """
            SELECT job_part_requirements.id, job_part_requirements.job_id, job_part_requirements.pulled_quantity,
                   jobs.warehouse_id
            FROM job_part_requirements
            JOIN jobs ON jobs.id = job_part_requirements.job_id
            WHERE job_part_requirements.id = ?
            """,
            (requirement_id,),
        ).fetchone()
        if requirement is None or int(requirement["job_id"]) != job_id or int(requirement["warehouse_id"]) != warehouse_id:
            return jsonify({"error": "Job part not found."}), 404
        if required_quantity <= 0:
            return jsonify({"error": "Required quantity must be at least 1."}), 400
        if required_quantity < int(requirement["pulled_quantity"]):
            return jsonify({"error": "Required quantity cannot be lower than the amount already pulled."}), 400
        validated_requirements.append((requirement_id, required_quantity, int(requirement["job_id"])))

    job_type = payload.get("jobType", "").strip()
    if job_type not in JOB_TYPE_OPTIONS:
        return jsonify({"error": "Choose a valid job type."}), 400
    service_job = is_service_job_type(job_type)
    detail_job = is_detail_job_type(job_type)
    actor_id = current_user_id(db)
    timestamp = datetime.now().isoformat()
    service_fields = normalize_service_job_payload(payload, job)
    if service_job:
        related_install = related_install_context(
            db,
            warehouse_id,
            contract_number=str(service_fields["contract_number"]),
            customer_name=str(service_fields["customer_name_primary"] or payload.get("customerName", "")),
            address=str(service_fields["address_line_1"] or payload.get("address", "")),
        )
        if related_install is not None:
            service_fields["sale_date"] = str(service_fields["sale_date"] or related_install["sale_date"] or "")
            service_fields["salesperson"] = str(service_fields["salesperson"] or related_install["salesperson"] or "")
            service_fields["install_date"] = str(service_fields["install_date"] or related_install["scheduled_for"] or related_install["install_date"] or "")
            service_fields["product_type"] = str(service_fields["product_type"] or related_install["product_type"] or "")
            service_fields["color"] = str(service_fields["color"] or related_install["color"] or "")
            service_fields["contract_number"] = str(service_fields["contract_number"] or related_install["contract_number"] or "")
        service_fields["customer_name_primary"] = str(service_fields["customer_name_primary"] or payload.get("customerName", "") or job["customer_name"])
        service_fields["address_line_1"] = str(service_fields["address_line_1"] or payload.get("address", "") or job["address"])
        service_fields["prior_visit_count"] = prior_service_visit_count(
            db,
            warehouse_id,
            contract_number=str(service_fields["contract_number"]),
            customer_name=str(service_fields["customer_name_primary"]),
            address=str(service_fields["address_line_1"]),
            exclude_job_id=job_id,
        )
        validation_error = validate_service_job_fields(service_fields)
        if validation_error:
            return jsonify({"error": validation_error}), 400
    else:
        service_fields = normalize_service_job_payload({}, job)
    status_value = str(service_fields["service_status"] if service_job else (payload.get("status") or job["status"] or "Active")).strip()
    if status_value not in JOB_STATUS_OPTIONS:
        status_value = "Active"
    db.execute(
        """
        UPDATE jobs
        SET job_number = ?, title = ?, customer_name = ?, address = ?, scheduled_for = ?, job_type = ?, technician = ?, assigned_user_id = ?, status = ?, notes = ?,
            service_code = ?, office_number = ?, zone_number = ?, contract_number = ?, call_date = ?, scheduled_time = ?,
            estimated_hours = ?, prior_visit_count = ?, customer_name_primary = ?, customer_name_secondary = ?, address_line_1 = ?,
            city = ?, state = ?, zip = ?, primary_phone = ?, secondary_phone = ?, email = ?, best_contact_note = ?, sale_date = ?, salesperson = ?,
            install_date = ?, product_type = ?, color = ?, customer_complaint = ?, dispatch_description = ?, probable_issue_category = ?,
            service_category = ?, urgency = ?, internal_notes = ?, return_trip_required = ?, return_reason = ?, return_estimated_hours = ?,
            survey_left = ?, parts_to_order = ?, service_cost = ?, payment_method = ?, no_payment_due = ?, start_time = ?, end_time = ?,
            travel_time_minutes = ?, total_time_minutes = ?, customer_comments = ?, customer_signature = ?, paid_service = ?,
            service_fault_category = ?, service_item = ?, service_issue = ?, manager_approval_name = ?, manager_approval_date = ?,
            return_for_credit = ?, service_record_id = ?, updated_by_user_id = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            payload["jobNumber"].strip(),
            payload["title"].strip(),
            payload.get("customerName", "").strip(),
            payload.get("address", "").strip(),
            payload.get("scheduledFor", "").strip(),
            job_type,
            payload.get("technician", "").strip() or (assigned_user["display_name"] if assigned_user else job["technician"]),
            int(assigned_user["id"]) if assigned_user is not None else None,
            status_value,
            payload.get("notes", "").strip(),
            service_fields["service_code"],
            service_fields["office_number"],
            service_fields["zone_number"],
            service_fields["contract_number"],
            service_fields["call_date"],
            service_fields["scheduled_time"],
            service_fields["estimated_hours"],
            int(service_fields["prior_visit_count"]),
            service_fields["customer_name_primary"],
            service_fields["customer_name_secondary"],
            service_fields["address_line_1"],
            service_fields["city"],
            service_fields["state"],
            service_fields["zip"],
            service_fields["primary_phone"],
            service_fields["secondary_phone"],
            service_fields["email"],
            service_fields["best_contact_note"],
            service_fields["sale_date"],
            service_fields["salesperson"],
            service_fields["install_date"],
            service_fields["product_type"],
            service_fields["color"],
            service_fields["customer_complaint"],
            service_fields["dispatch_description"],
            service_fields["probable_issue_category"],
            service_fields["service_category"],
            service_fields["urgency"],
            service_fields["internal_notes"],
            service_fields["return_trip_required"],
            service_fields["return_reason"],
            service_fields["return_estimated_hours"],
            service_fields["survey_left"],
            service_fields["parts_to_order"],
            service_fields["service_cost"],
            service_fields["payment_method"],
            service_fields["no_payment_due"],
            service_fields["start_time"],
            service_fields["end_time"],
            int(service_fields["travel_time_minutes"]),
            int(service_fields["total_time_minutes"]),
            service_fields["customer_comments"],
            service_fields["customer_signature"],
            service_fields["paid_service"],
            service_fields["service_fault_category"],
            service_fields["service_item"],
            service_fields["service_issue"],
            service_fields["manager_approval_name"],
            service_fields["manager_approval_date"],
            service_fields["return_for_credit"],
            service_fields["service_record_id"],
            actor_id,
            timestamp,
            job_id,
        ),
    )
    for requirement_id, required_quantity, _job_id in validated_requirements:
        db.execute(
            "UPDATE job_part_requirements SET required_quantity = ?, updated_by_user_id = ?, updated_at = ? WHERE id = ?",
            (required_quantity, actor_id, timestamp, requirement_id),
        )
    if detail_job:
        apply_detail_job_fields(db, job_id, normalize_detail_job_payload(payload, job), actor_id)
    refresh_job_status(db, job_id)
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/jobs/<int:job_id>/complete")
@permission_required("complete_jobs")
def complete_job(job_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    job = job_with_access(db, job_id, warehouse_id)
    if job is None:
        return jsonify({"error": "Job not found or not assigned to you."}), 404

    recipient_name = payload.get("recipientName", "").strip()
    recipient_email = payload.get("recipientEmail", "").strip()
    work_performed = payload.get("workPerformed", "").strip()
    completion_notes = payload.get("completionNotes", "").strip()
    send_email = bool(payload.get("sendEmail"))
    preview = build_completion_preview(db, job, recipient_name, recipient_email, work_performed, completion_notes)
    if send_email and not recipient_email:
        return jsonify({"error": "Enter a recipient email before sending."}), 400
    attachments = job_attachment_rows(db, job_id)
    email_sent_at = ""
    actor_id = current_user_id(db)
    service_fields = normalize_service_job_payload(payload, job)
    detail_fields = normalize_detail_job_payload(payload, job)
    status_after_completion = "Completed"
    if is_service_job_type(job["job_type"]):
        service_fields["prior_visit_count"] = prior_service_visit_count(
            db,
            warehouse_id,
            contract_number=str(service_fields["contract_number"] or job["contract_number"]),
            customer_name=str(service_fields["customer_name_primary"] or job["customer_name_primary"] or job["customer_name"]),
            address=str(service_fields["address_line_1"] or job["address_line_1"] or job["address"]),
            exclude_job_id=job_id,
        )
        if service_fields["return_trip_required"] == "Yes":
            status_after_completion = "Return Trip Needed"
        validation_error = validate_service_job_fields(service_fields)
        if validation_error:
            return jsonify({"error": validation_error}), 400
    if send_email:
        try:
            send_completion_email(preview, job_id, attachments)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        except OSError as error:
            return jsonify({"error": f"Email send failed: {error}"}), 400
        email_sent_at = datetime.now().isoformat()
    completed_at = datetime.now().isoformat()
    db.execute(
        """
        UPDATE jobs
        SET status = ?, notes = ?, completion_notes = ?, completion_work_performed = ?,
            completion_recipient_name = ?, completion_recipient_email = ?, completion_email_subject = ?,
            completion_email_body = ?, completed_at = ?, completed_by_user_id = ?, updated_by_user_id = ?, updated_at = ?, completion_email_sent_at = ?,
            call_date = ?, scheduled_time = ?, estimated_hours = ?, prior_visit_count = ?,
            primary_phone = ?, secondary_phone = ?, email = ?, best_contact_note = ?,
            customer_complaint = ?, dispatch_description = ?, probable_issue_category = ?, service_category = ?, urgency = ?, internal_notes = ?,
            return_trip_required = ?, return_reason = ?, return_estimated_hours = ?, survey_left = ?, parts_to_order = ?,
            service_cost = ?, payment_method = ?, no_payment_due = ?, start_time = ?, end_time = ?, travel_time_minutes = ?, total_time_minutes = ?,
            customer_comments = ?, customer_signature = ?, paid_service = ?, service_fault_category = ?, service_item = ?, service_issue = ?,
            manager_approval_name = ?, manager_approval_date = ?, return_for_credit = ?, service_record_id = ?
        WHERE id = ?
        """,
        (
            status_after_completion,
            (payload.get("notes", "").strip() or job["notes"]),
            completion_notes,
            work_performed,
            recipient_name,
            recipient_email,
            preview["subject"],
            preview["body"],
            completed_at,
            actor_id,
            actor_id,
            completed_at,
            email_sent_at,
            service_fields["call_date"],
            service_fields["scheduled_time"],
            service_fields["estimated_hours"],
            int(service_fields["prior_visit_count"]),
            service_fields["primary_phone"],
            service_fields["secondary_phone"],
            service_fields["email"],
            service_fields["best_contact_note"],
            service_fields["customer_complaint"],
            service_fields["dispatch_description"],
            service_fields["probable_issue_category"],
            service_fields["service_category"],
            service_fields["urgency"],
            service_fields["internal_notes"],
            service_fields["return_trip_required"],
            service_fields["return_reason"],
            service_fields["return_estimated_hours"],
            service_fields["survey_left"],
            service_fields["parts_to_order"],
            service_fields["service_cost"],
            service_fields["payment_method"],
            service_fields["no_payment_due"],
            service_fields["start_time"],
            service_fields["end_time"],
            int(service_fields["travel_time_minutes"]),
            int(service_fields["total_time_minutes"]),
            service_fields["customer_comments"],
            service_fields["customer_signature"],
            service_fields["paid_service"],
            service_fields["service_fault_category"],
            service_fields["service_item"],
            service_fields["service_issue"],
            service_fields["manager_approval_name"],
            service_fields["manager_approval_date"],
            service_fields["return_for_credit"],
            service_fields["service_record_id"],
            job_id,
        ),
    )
    if is_detail_job_type(job["job_type"]):
        apply_detail_job_fields(db, job_id, detail_fields, actor_id)
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/jobs/<int:job_id>/follow-up")
@permission_required("edit_records")
def create_follow_up_service_job(job_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    source_job = db.execute(
        "SELECT * FROM jobs WHERE id = ? AND warehouse_id = ?",
        (job_id, warehouse_id),
    ).fetchone()
    if source_job is None:
        return jsonify({"error": "Service job not found."}), 404
    if not is_service_job_type(source_job["job_type"]):
        return jsonify({"error": "Follow-up jobs can only be created from service or warranty tickets."}), 400

    timestamp = datetime.now().isoformat()
    actor_id = current_user_id(db)
    base_job_number = str(source_job["job_number"] or "SERVICE").strip() or "SERVICE"
    suffix_number = 1
    follow_up_job_number = f"{base_job_number}-RT{suffix_number}"
    while db.execute("SELECT 1 FROM jobs WHERE warehouse_id = ? AND job_number = ?", (warehouse_id, follow_up_job_number)).fetchone():
        suffix_number += 1
        follow_up_job_number = f"{base_job_number}-RT{suffix_number}"

    service_fields = normalize_service_job_payload({}, source_job)
    service_fields["prior_visit_count"] = prior_service_visit_count(
        db,
        warehouse_id,
        contract_number=str(service_fields["contract_number"] or source_job["contract_number"] or ""),
        customer_name=str(service_fields["customer_name_primary"] or source_job["customer_name_primary"] or source_job["customer_name"] or ""),
        address=str(service_fields["address_line_1"] or source_job["address_line_1"] or source_job["address"] or ""),
    )
    service_fields["return_trip_required"] = "Unknown"
    service_fields["return_reason"] = ""
    scheduled_for = datetime.now().date().isoformat()

    cursor = db.execute(
        """
        INSERT INTO jobs (
            warehouse_id, job_number, title, customer_name, address, scheduled_for,
            job_type, technician, assigned_user_id, status, notes,
            service_code, office_number, zone_number, contract_number, call_date, scheduled_time,
            estimated_hours, prior_visit_count, customer_name_primary, customer_name_secondary, address_line_1,
            city, state, zip, primary_phone, secondary_phone, email, best_contact_note, sale_date, salesperson,
            install_date, product_type, color, customer_complaint, dispatch_description, probable_issue_category,
            service_category, urgency, internal_notes, return_trip_required, return_reason, return_estimated_hours,
            survey_left, parts_to_order, service_cost, payment_method, no_payment_due, start_time, end_time,
            travel_time_minutes, total_time_minutes, customer_comments, customer_signature, paid_service,
            service_fault_category, service_item, service_issue, manager_approval_name, manager_approval_date,
            return_for_credit, service_record_id,
            created_by_user_id, updated_by_user_id, updated_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            warehouse_id,
            follow_up_job_number,
            str(source_job["title"] or "Service Follow-Up").strip(),
            str(source_job["customer_name"] or "").strip(),
            str(source_job["address"] or "").strip(),
            scheduled_for,
            str(source_job["job_type"] or "Service"),
            str(source_job["technician"] or "Unassigned"),
            source_job["assigned_user_id"],
            "Scheduled",
            f"Follow-up created from {base_job_number} on {datetime.now().date().isoformat()}.".strip(),
            service_fields["service_code"],
            service_fields["office_number"],
            service_fields["zone_number"],
            service_fields["contract_number"],
            timestamp[:10],
            service_fields["scheduled_time"],
            service_fields["estimated_hours"],
            int(service_fields["prior_visit_count"]),
            service_fields["customer_name_primary"],
            service_fields["customer_name_secondary"],
            service_fields["address_line_1"],
            service_fields["city"],
            service_fields["state"],
            service_fields["zip"],
            service_fields["primary_phone"],
            service_fields["secondary_phone"],
            service_fields["email"],
            service_fields["best_contact_note"],
            service_fields["sale_date"],
            service_fields["salesperson"],
            service_fields["install_date"],
            service_fields["product_type"],
            service_fields["color"],
            service_fields["customer_complaint"],
            service_fields["dispatch_description"],
            service_fields["probable_issue_category"],
            service_fields["service_category"],
            service_fields["urgency"],
            service_fields["internal_notes"],
            service_fields["return_trip_required"],
            service_fields["return_reason"],
            service_fields["return_estimated_hours"],
            service_fields["survey_left"],
            service_fields["parts_to_order"],
            service_fields["service_cost"],
            service_fields["payment_method"],
            service_fields["no_payment_due"],
            "",
            "",
            0,
            0,
            "",
            "",
            service_fields["paid_service"],
            service_fields["service_fault_category"],
            service_fields["service_item"],
            service_fields["service_issue"],
            "",
            "",
            service_fields["return_for_credit"],
            str(source_job["service_record_id"] or source_job["job_number"] or ""),
            actor_id,
            actor_id,
            timestamp,
            timestamp,
        ),
    )
    db.commit()
    return jsonify({"createdJobId": int(cursor.lastrowid), "state": bootstrap_payload(warehouse_id)})


@app.post("/api/jobs/<int:job_id>/completion-preview")
@permission_required("complete_jobs")
def preview_job_completion(job_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    job = job_with_access(db, job_id, warehouse_id)
    if job is None:
        return jsonify({"error": "Job not found or not assigned to you."}), 404
    preview = build_completion_preview(
        db,
        job,
        payload.get("recipientName", "").strip(),
        payload.get("recipientEmail", "").strip(),
        payload.get("workPerformed", "").strip(),
        payload.get("completionNotes", "").strip(),
    )
    return jsonify({"preview": preview})


@app.post("/api/jobs/<int:job_id>/notes")
@permission_required("notes_access")
def update_job_notes(job_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    job = job_with_access(db, job_id, warehouse_id)
    if job is None:
        return jsonify({"error": "Job not found or not assigned to you."}), 404
    db.execute(
        "UPDATE jobs SET notes = ?, updated_by_user_id = ?, updated_at = ? WHERE id = ?",
        (payload.get("notes", "").strip(), current_user_id(db), datetime.now().isoformat(), job_id),
    )
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/jobs/<int:job_id>/quick-notes")
@permission_required("notes_access")
def add_job_quick_note(job_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    job = job_with_access(db, job_id, warehouse_id)
    if job is None:
        return jsonify({"error": "Job not found or not assigned to you."}), 404
    body = str(payload.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Enter a note before saving."}), 400
    user = current_user_record(db)
    timestamp = datetime.now().isoformat()
    db.execute(
        """
        INSERT INTO job_notes (job_id, body, note_author_user_id, note_author, created_at, updated_at, updated_by_user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (job_id, body, current_user_id(db), str(user["display_name"]) if user is not None else "", timestamp, timestamp, current_user_id(db)),
    )
    db.execute(
        "UPDATE jobs SET updated_by_user_id = ?, updated_at = ? WHERE id = ?",
        (current_user_id(db), timestamp, job_id),
    )
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/job-notes/<int:note_id>")
@permission_required("notes_access")
def update_job_quick_note(note_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    note = db.execute(
        """
        SELECT job_notes.*, jobs.warehouse_id, jobs.assigned_user_id
        FROM job_notes
        JOIN jobs ON jobs.id = job_notes.job_id
        WHERE job_notes.id = ?
        """,
        (note_id,),
    ).fetchone()
    if note is None or int(note["warehouse_id"]) != warehouse_id or not manager_or_assigned_job(note):
        return jsonify({"error": "Note not found or not assigned to you."}), 404
    body = str(payload.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Note text cannot be empty."}), 400
    timestamp = datetime.now().isoformat()
    db.execute(
        "UPDATE job_notes SET body = ?, updated_at = ?, updated_by_user_id = ? WHERE id = ?",
        (body, timestamp, current_user_id(db), note_id),
    )
    db.execute(
        "UPDATE jobs SET updated_by_user_id = ?, updated_at = ? WHERE id = ?",
        (current_user_id(db), timestamp, int(note["job_id"])),
    )
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/jobs/<int:job_id>/attachments")
def upload_job_attachment(job_id: int):
    db = get_db()
    job = job_with_access(db, job_id)
    if job is None:
        return jsonify({"error": "Job not found or not assigned to you."}), 404

    attachment = request.files.get("attachment")
    if attachment is None:
        return jsonify({"error": "Choose a file to upload."}), 400

    try:
        destination, original_name, file_size = store_job_attachment(attachment, job_id)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    content_type = (attachment.mimetype or mimetypes.guess_type(original_name)[0] or "").strip()
    current_user = current_user_record(db)
    storage_path = str(destination.relative_to(BASE_DIR))
    db.execute(
        """
        INSERT INTO job_attachments (
            job_id, original_name, stored_name, storage_path, content_type, file_size, uploaded_by_user_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            original_name,
            destination.name,
            storage_path,
            content_type,
            file_size,
            int(current_user["id"]) if current_user is not None else None,
            datetime.now().isoformat(),
        ),
    )
    if is_detail_job_type(job["job_type"]):
        text, extraction_flags = extract_text_from_attachment(destination, original_name)
        if text.strip() or extraction_flags:
            latest_job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            apply_detail_job_fields(db, job_id, derive_detail_extraction(latest_job, text, extraction_flags), current_user_id(db))
    db.commit()
    return jsonify(bootstrap_payload(int(job["warehouse_id"])))


@app.get("/api/job-attachments/<int:attachment_id>/view")
@login_required
def view_job_attachment(attachment_id: int):
    db = get_db()
    attachment = attachment_with_access(db, attachment_id)
    if attachment is None:
        return auth_error("Attachment not found or not assigned to you.", 404)

    attachment_path = (BASE_DIR / str(attachment["storage_path"])).resolve()
    try:
        attachment_path.relative_to(ATTACHMENTS_DIR.resolve())
    except ValueError:
        return auth_error("Attachment path is invalid.", 400)
    if not attachment_path.exists():
        return auth_error("Attachment file is missing.", 404)

    return send_file(
        BytesIO(attachment_path.read_bytes()),
        mimetype=str(attachment["content_type"] or mimetypes.guess_type(str(attachment_path))[0] or "application/octet-stream"),
        download_name=str(attachment["original_name"]),
        as_attachment=False,
    )


@app.get("/api/job-attachments/<int:attachment_id>/download")
@login_required
def download_job_attachment(attachment_id: int):
    db = get_db()
    attachment = attachment_with_access(db, attachment_id)
    if attachment is None:
        return auth_error("Attachment not found or not assigned to you.", 404)

    attachment_path = (BASE_DIR / str(attachment["storage_path"])).resolve()
    try:
        attachment_path.relative_to(ATTACHMENTS_DIR.resolve())
    except ValueError:
        return auth_error("Attachment path is invalid.", 400)
    if not attachment_path.exists():
        return auth_error("Attachment file is missing.", 404)

    return send_file(
        BytesIO(attachment_path.read_bytes()),
        mimetype=str(attachment["content_type"] or mimetypes.guess_type(str(attachment_path))[0] or "application/octet-stream"),
        download_name=str(attachment["original_name"]),
        as_attachment=True,
    )


@app.post("/api/job-attachments/<int:attachment_id>/delete")
@permission_required("delete_records")
def delete_job_attachment(attachment_id: int):
    db = get_db()
    attachment = attachment_with_access(db, attachment_id)
    if attachment is None:
        return jsonify({"error": "Attachment not found."}), 404

    attachment_path = (BASE_DIR / str(attachment["storage_path"])).resolve()
    try:
        attachment_path.relative_to(ATTACHMENTS_DIR.resolve())
    except ValueError:
        return jsonify({"error": "Attachment path is invalid."}), 400

    db.execute("DELETE FROM job_attachments WHERE id = ?", (attachment_id,))
    db.commit()
    if attachment_path.exists():
        attachment_path.unlink()
    return jsonify(bootstrap_payload(int(attachment["warehouse_id"])))


@app.post("/api/jobs/<int:job_id>/parts")
@permission_required("edit_records")
def add_job_part(job_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    part_id = int(payload["partId"])
    required_quantity = int(payload["requiredQuantity"])
    if required_quantity <= 0:
        return jsonify({"error": "Quantity must be at least 1."}), 400

    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id = ? AND warehouse_id = ?", (job_id, warehouse_id)).fetchone()
    if job is None:
        return jsonify({"error": "Job not found."}), 404
    part = db.execute("SELECT * FROM parts WHERE id = ? AND warehouse_id = ?", (part_id, warehouse_id)).fetchone()
    if part is None:
        return jsonify({"error": "Part not found in this warehouse."}), 404

    actor_id = current_user_id(db)
    timestamp = datetime.now().isoformat()
    existing = db.execute(
        "SELECT * FROM job_part_requirements WHERE job_id = ? AND part_id = ?",
        (job_id, part_id),
    ).fetchone()
    if existing is None:
        db.execute(
            """
            INSERT INTO job_part_requirements (
                job_id, part_id, required_quantity, pulled_quantity, created_by_user_id, updated_by_user_id, updated_at, created_at
            )
            VALUES (?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (job_id, part_id, required_quantity, actor_id, actor_id, timestamp, timestamp),
        )
    else:
        db.execute(
            "UPDATE job_part_requirements SET required_quantity = required_quantity + ?, updated_by_user_id = ?, updated_at = ? WHERE id = ?",
            (required_quantity, actor_id, timestamp, existing["id"]),
        )
    db.execute("UPDATE jobs SET updated_by_user_id = ?, updated_at = ? WHERE id = ?", (actor_id, timestamp, job_id))
    refresh_job_status(db, job_id)
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/job-parts/<int:requirement_id>")
@permission_required("edit_records")
def update_job_requirement(requirement_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    required_quantity = int(payload["requiredQuantity"])
    db = get_db()
    requirement = db.execute(
        """
        SELECT job_part_requirements.*, jobs.warehouse_id
        FROM job_part_requirements
        JOIN jobs ON jobs.id = job_part_requirements.job_id
        WHERE job_part_requirements.id = ?
        """,
        (requirement_id,),
    ).fetchone()
    if requirement is None or requirement["warehouse_id"] != warehouse_id:
        return jsonify({"error": "Job part not found."}), 404
    if required_quantity < requirement["pulled_quantity"]:
        return jsonify({"error": "Required quantity cannot be lower than the amount already pulled."}), 400

    timestamp = datetime.now().isoformat()
    db.execute(
        "UPDATE job_part_requirements SET required_quantity = ?, updated_by_user_id = ?, updated_at = ? WHERE id = ?",
        (required_quantity, current_user_id(db), timestamp, requirement_id),
    )
    db.execute("UPDATE jobs SET updated_by_user_id = ?, updated_at = ? WHERE id = ?", (current_user_id(db), timestamp, requirement["job_id"]))
    refresh_job_status(db, requirement["job_id"])
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/job-parts/<int:requirement_id>/delete")
@permission_required("delete_records")
def delete_job_requirement(requirement_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    db = get_db()
    requirement = db.execute(
        """
        SELECT job_part_requirements.*, jobs.warehouse_id
        FROM job_part_requirements
        JOIN jobs ON jobs.id = job_part_requirements.job_id
        WHERE job_part_requirements.id = ?
        """,
        (requirement_id,),
    ).fetchone()
    if requirement is None or requirement["warehouse_id"] != warehouse_id:
        return jsonify({"error": "Job part not found."}), 404
    if requirement["pulled_quantity"] > 0:
        return jsonify({"error": "Only unpulled parts can be removed from a job."}), 400

    db.execute("DELETE FROM job_part_requirements WHERE id = ?", (requirement_id,))
    db.execute(
        "UPDATE jobs SET updated_by_user_id = ?, updated_at = ? WHERE id = ?",
        (current_user_id(db), datetime.now().isoformat(), requirement["job_id"]),
    )
    refresh_job_status(db, requirement["job_id"])
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))



@app.post("/api/parts/scan-match")
@permission_required("inventory_access")
def scan_match_part():
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    scan_value = normalize_scan_code(payload.get("scanValue", ""))
    if not scan_value:
        return jsonify({"error": "Scan a barcode, QR code, or internal scan code first."}), 400

    db = get_db()
    part = scanned_part_for_job(db, warehouse_id, scan_value)
    if part is None:
        return jsonify({"error": f"No inventory item matched scan code {scan_value}."}), 404

    open_job_count_row = db.execute(
        """
        SELECT COUNT(DISTINCT jobs.id) AS total
        FROM job_part_requirements
        JOIN jobs ON jobs.id = job_part_requirements.job_id
        WHERE jobs.warehouse_id = ?
          AND jobs.status != 'Completed'
          AND job_part_requirements.part_id = ?
        """,
        (warehouse_id, int(part["id"])),
    ).fetchone()
    vendor_name_row = db.execute("SELECT name FROM vendors WHERE id = ?", (int(part["vendor_id"]),)).fetchone()
    part_payload = serialize_scanned_part(part)
    part_payload["vendorName"] = vendor_name_row["name"] if vendor_name_row else ""
    part_payload["openJobCount"] = int(open_job_count_row["total"]) if open_job_count_row else 0
    return jsonify({"part": part_payload})


@app.post("/api/jobs/<int:job_id>/scan-match")
def scan_match_for_job(job_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    scan_value = normalize_scan_code(payload.get("scanValue", ""))
    if not scan_value:
        return jsonify({"error": "Scan a barcode, QR code, or internal scan code first."}), 400

    db = get_db()
    job = job_with_access(db, job_id, warehouse_id)
    if job is None:
        return jsonify({"error": "Job not found or not assigned to you."}), 404

    part = scanned_part_for_job(db, warehouse_id, scan_value)
    if part is None:
        return jsonify({"error": f"No inventory item matched scan code {scan_value}."}), 404

    requirement = requirement_for_job_part(db, job_id, int(part["id"]))

    return jsonify({
        "job": {
            "id": int(job["id"]),
            "jobNumber": job["job_number"],
            "technician": job["technician"],
        },
        "part": serialize_scanned_part(part, requirement),
    })


@app.post("/api/jobs/<int:job_id>/scan-pull")
def scan_pull_for_job(job_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    part_id = int(payload["partId"])
    quantity = int(payload["quantity"])
    action = (payload.get("action") or "job_requirement").strip()
    confirm_overpull = bool(payload.get("confirmOverpull"))
    if quantity <= 0:
        return jsonify({"error": "Pull quantity must be at least 1."}), 400

    db = get_db()
    begin_immediate_transaction(db)
    job = job_with_access(db, job_id, warehouse_id)
    if job is None:
        db.rollback()
        return jsonify({"error": "Job not found or not assigned to you."}), 404

    part = db.execute("SELECT * FROM parts WHERE id = ? AND warehouse_id = ?", (part_id, warehouse_id)).fetchone()
    if part is None:
        db.rollback()
        return jsonify({"error": "Part not found in this warehouse."}), 404
    if quantity > int(part["stock"]):
        db.rollback()
        return jsonify({"error": "Not enough inventory on hand for that pull."}), 400

    requirement = requirement_for_job_part(db, job_id, part_id)
    remaining = max((int(requirement["required_quantity"]) - int(requirement["pulled_quantity"])) if requirement else 0, 0)
    timestamp = datetime.now().isoformat()
    note_suffix = payload.get("scanValue", "").strip() or part["scan_code"] or part["part_number"]

    if requirement is None:
        if action == "add_to_job":
            db.execute(
                """
                INSERT INTO job_part_requirements (
                    job_id, part_id, required_quantity, pulled_quantity, created_by_user_id, updated_by_user_id, updated_at, created_at
                )
                VALUES (?, ?, ?, 0, ?, ?, ?, ?)
                """,
                (job_id, part_id, quantity, current_user_id(db), current_user_id(db), timestamp, timestamp),
            )
            requirement = requirement_for_job_part(db, job_id, part_id)
            if requirement is None:
                db.rollback()
                return jsonify({"error": "Unable to add the scanned part to the job."}), 500
            pull_requirement_quantity(
                db,
                requirement,
                quantity,
                payload.get("notes", "").strip() or f"Scanned pull after adding part to job ({note_suffix})",
            )
            action_label = "Added to job and pulled"
        elif action == "misc_usage":
            stock_update = db.execute("UPDATE parts SET stock = stock - ? WHERE id = ? AND stock >= ?", (quantity, part_id, quantity))
            if stock_update.rowcount != 1:
                db.rollback()
                return jsonify({"error": "Not enough inventory on hand for that pull."}), 400
            log_job_usage(
                db,
                warehouse_id,
                str(job["job_number"]),
                str(job["technician"]),
                part_id,
                quantity,
                payload.get("notes", "").strip() or f"Scanned miscellaneous usage ({note_suffix})",
            )
            refresh_job_status(db, job_id)
            action_label = "Marked as miscellaneous usage"
        else:
            db.rollback()
            return jsonify({"error": "That scanned part is not assigned to this job yet."}), 400
    else:
        if quantity > remaining and not confirm_overpull:
            db.rollback()
            return jsonify({"error": f"This pull exceeds the remaining quantity needed ({remaining}). Confirm the over-pull to continue."}), 400
        try:
            pull_requirement_quantity(
                db,
                requirement,
                quantity,
                payload.get("notes", "").strip() or f"Scanned pull ({note_suffix})",
                allow_overpull=confirm_overpull,
            )
        except ValueError as error:
            db.rollback()
            return jsonify({"error": str(error)}), 400
        action_label = "Pulled for job" if quantity <= remaining else "Over-pull confirmed"

    db.commit()
    return jsonify({
        "state": bootstrap_payload(warehouse_id),
        "scanLogEntry": {
            "timestamp": timestamp,
            "partNumber": part["part_number"],
            "description": part["description"],
            "quantity": quantity,
            "action": action_label,
            "scanCode": payload.get("scanValue", "").strip() or part["scan_code"],
        },
    })


@app.post("/api/job-parts/<int:requirement_id>/pull")
def pull_job_part(requirement_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    quantity = int(payload["quantity"])
    if quantity <= 0:
        return jsonify({"error": "Pull quantity must be at least 1."}), 400

    db = get_db()
    begin_immediate_transaction(db)
    requirement = requirement_with_access(db, requirement_id)
    if requirement is None or requirement["warehouse_id"] != warehouse_id:
        db.rollback()
        return jsonify({"error": "Job requirement not found or not assigned to you."}), 404

    try:
        pull_requirement_quantity(
            db,
            requirement,
            quantity,
            payload.get("notes", "").strip() or "Pulled for job",
        )
    except ValueError as error:
        db.rollback()
        return jsonify({"error": str(error)}), 400
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/job-parts/<int:requirement_id>/receive-direct")
@permission_required("receive_jobs")
def receive_job_part_direct(requirement_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    quantity = int(payload["quantity"])
    if quantity <= 0:
        return jsonify({"error": "Receive quantity must be at least 1."}), 400

    db = get_db()
    requirement = requirement_with_access(db, requirement_id)
    if requirement is None or requirement["warehouse_id"] != warehouse_id:
        return jsonify({"error": "Job requirement not found or not assigned to you."}), 404

    try:
        receive_requirement_direct_to_job(
            db,
            requirement,
            quantity,
            payload.get("notes", "").strip() or "Received direct to job",
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/job-parts/<int:requirement_id>/return")
def return_job_part(requirement_id: int):
    payload = request.get_json(force=True)
    warehouse_id = int(payload["warehouseId"])
    quantity = int(payload["quantity"])
    if quantity <= 0:
        return jsonify({"error": "Return quantity must be at least 1."}), 400

    db = get_db()
    requirement = requirement_with_access(db, requirement_id)
    if requirement is None or requirement["warehouse_id"] != warehouse_id:
        return jsonify({"error": "Job requirement not found or not assigned to you."}), 404

    if quantity > requirement["pulled_quantity"]:
        return jsonify({"error": f"Only {requirement['pulled_quantity']} pulled part(s) can be returned."}), 400

    db.execute("UPDATE parts SET stock = stock + ? WHERE id = ?", (quantity, requirement["part_id"]))
    db.execute(
        "UPDATE job_part_requirements SET pulled_quantity = pulled_quantity - ?, updated_by_user_id = ?, updated_at = ? WHERE id = ?",
        (quantity, current_user_id(db), datetime.now().isoformat(), requirement_id),
    )
    log_job_usage(
        db,
        warehouse_id,
        requirement["job_number"],
        requirement["technician"],
        requirement["part_id"],
        -quantity,
        payload.get("notes", "").strip() or "Returned from job",
    )
    db.execute(
        "UPDATE jobs SET updated_by_user_id = ?, updated_at = ? WHERE id = ?",
        (current_user_id(db), datetime.now().isoformat(), requirement["job_id"]),
    )
    refresh_job_status(db, requirement["job_id"])
    db.commit()
    return jsonify(bootstrap_payload(warehouse_id))


@app.post("/api/reset")
@permission_required("edit_records")
def api_reset():
    db = get_db()
    seed_database(db)
    return jsonify(bootstrap_payload(selected_warehouse_id()))


@app.post("/api/transfers")
@permission_required("edit_records")
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
                (warehouse_id, part_number, scan_code, description, category, stock, reorder_point, vendor_id, unit_cost)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                to_warehouse_id,
                part["part_number"],
                part["scan_code"],
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
@permission_required("reporting_access")
def api_export():
    warehouse_id = selected_warehouse_id()
    export_path = BASE_DIR / "instance" / "shopflow-export.json"
    export_path.write_text(json.dumps(bootstrap_payload(warehouse_id), indent=2), encoding="utf-8")
    return send_file(
        export_path,
        as_attachment=True,
        download_name=f"shopflow-export-{datetime.now().date().isoformat()}-{warehouse_id}.json",
    )


init_db()


if __name__ == "__main__":
    host = os.environ.get("SHOPFLOW_DEV_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.environ.get("SHOPFLOW_DEV_PORT", "5000") or 5000)
    debug = os.environ.get("SHOPFLOW_DEBUG", "1").strip().lower() not in {"0", "false", "no"}
    app.run(host=host, port=port, debug=debug)



