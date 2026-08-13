from __future__ import annotations

import os
import time

# Corporate order forms should use Davenport's business date even when hosted on UTC servers.
os.environ.setdefault("TZ", "America/Chicago")
if hasattr(time, "tzset"):
    time.tzset()

from app import BASE_DIR, DB_PATH, app, current_user_can
from office93_catalog import register_office93_catalog
from order_form_plugin import register_order_form_plugin

register_office93_catalog(
    app,
    db_path=DB_PATH,
    base_dir=BASE_DIR,
    permission_checker=lambda permission: current_user_can(permission),
)

register_order_form_plugin(
    app,
    db_path=DB_PATH,
    base_dir=BASE_DIR,
    permission_checker=lambda permission: current_user_can(permission),
)
