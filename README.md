# ShopFlow Inventory

ShopFlow is a Python web app starter for shop inventory, purchasing, receiving, and job usage tracking.

## Stack

- Python 3.12
- Flask
- SQLite
- Vanilla HTML, CSS, and JavaScript

## Current features

- Warehouse selector that filters inventory, orders, receiving, and usage by location
- Warehouse management screen for adding and editing locations
- Warehouse archive and restore actions
- Parts catalog with location, vendor, stock, reorder point, and unit cost
- Vendor directory
- Safe delete actions for unused parts and vendors
- Stock transfers between warehouses with transfer history
- Purchase order creation
- Partial or full receiving against open purchase orders
- Job allocation and part usage tracking
- Low-stock dashboard visibility
- JSON export of current data
- Resettable demo seed data

## Run locally

1. Install dependencies:
   `python -m pip install -r requirements.txt`
2. Start the app:
   `python app.py`
3. Open:
   `http://127.0.0.1:5000`

The SQLite database is created automatically at `instance/shopflow.db`.

## Project files

- [app.py](C:\Users\blief\Documents\New project\app.py): Flask app, SQLite schema, seed data, and API routes
- [templates/index.html](C:\Users\blief\Documents\New project\templates\index.html): main app shell
- [assets/app.js](C:\Users\blief\Documents\New project\assets\app.js): frontend logic and API calls
- [assets/styles.css](C:\Users\blief\Documents\New project\assets\styles.css): UI styling

## Recommended next upgrades

1. Add real workplace fields like equipment, site, requester, and cost center.
2. Add authentication and user roles.
3. Add barcode scanning, warehouse transfers, and faster receiving workflows.
4. Add warehouse management screens if you want to maintain locations in the app.
5. Split the backend into modules as the app grows.
6. Move from local SQLite to PostgreSQL when you want multi-user deployment.
