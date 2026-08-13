from __future__ import annotations

from app import BASE_DIR, DB_PATH, app, current_user_can
from order_form_plugin import register_order_form_plugin

register_order_form_plugin(
    app,
    db_path=DB_PATH,
    base_dir=BASE_DIR,
    permission_checker=lambda permission: current_user_can(permission),
)
