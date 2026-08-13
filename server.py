from __future__ import annotations

import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

# Keep legacy local-time behavior for code that still relies on the process timezone.
os.environ.setdefault("TZ", "America/Chicago")
if hasattr(time, "tzset"):
    time.tzset()

from app import BASE_DIR, DB_PATH, app, current_user_can
from corporate_order_workflow import register_corporate_order_workflow
from office93_catalog import register_office93_catalog
from office93_cleanup import cleanup_demo_seed_data, disable_demo_reset
from office93_lumber_reference import sync_lumber_reference_items
import order_form_plugin as corporate_order_forms
from order_form_plugin import register_order_form_plugin


# Windows does not honor the POSIX TZ environment variable the same way Linux does,
# and hosted servers commonly run in UTC. Force every corporate order-form date to
# use Davenport's America/Chicago business date regardless of the machine clock.
OFFICE_TIMEZONE = ZoneInfo("America/Chicago")


class DavenportBusinessDate:
    @classmethod
    def today(cls):
        return datetime.now(OFFICE_TIMEZONE).date()


corporate_order_forms.date = DavenportBusinessDate

# One-time conversion from the old demo database to a clean Office 93 pilot database.
# The manager login is preserved; demo warehouses, transactions, vendors, parts,
# forms, and generated test users are removed before the real catalog is rebuilt.
cleanup_demo_seed_data(DB_PATH)

register_office93_catalog(
    app,
    db_path=DB_PATH,
    base_dir=BASE_DIR,
    permission_checker=lambda permission: current_user_can(permission),
)

# The consolidated lumber sheet is reference-only for catalog seeding. It fills
# canonical REM/SND/TOL/WHSE item IDs that are awkward to parse reliably from
# the separate Lowe's/Home Depot/84 Lumber layouts, while preserving any real
# stock counts entered after the one-time demo cleanup.
sync_lumber_reference_items(DB_PATH)

register_order_form_plugin(
    app,
    db_path=DB_PATH,
    base_dir=BASE_DIR,
    permission_checker=lambda permission: current_user_can(permission),
)

# Corporate PDF generation now feeds the existing ShopFlow PO workflow instead of
# bypassing it. Generated orders begin Email Pending, require the Email Sent
# confirmation, then remain Waiting for Part until receiving closes them out.
register_corporate_order_workflow(app, db_path=DB_PATH)

disable_demo_reset(app)
