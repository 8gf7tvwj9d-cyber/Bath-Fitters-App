from __future__ import annotations

import os
import time

# Corporate order forms should use Davenport's business date even when hosted on UTC servers.
os.environ.setdefault("TZ", "America/Chicago")
if hasattr(time, "tzset"):
    time.tzset()

from app import BASE_DIR, DB_PATH, app, current_user_can
from office93_catalog import register_office93_catalog
from office93_cleanup import cleanup_demo_seed_data, disable_demo_reset
from office93_lumber_reference import sync_lumber_reference_items
from order_form_plugin import register_order_form_plugin

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

disable_demo_reset(app)
