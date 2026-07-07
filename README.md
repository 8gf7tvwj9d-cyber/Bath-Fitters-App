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
2. Install frontend tooling if you want to run lint/format checks:
   `npm install`
3. Run the lightweight deployment check:
   `npm run build`
4. Start the app:
   `python app.py`
5. Open:
   `http://127.0.0.1:5000`

For Windows, you can also just run:
`start_app.bat`

`start_app.bat` now uses Waitress for a more production-friendly Windows app server instead of relying on Flask's built-in development server.

## Private iPad / Phone access

The safest first mobile setup for this app is private access through Tailscale.

Why this is the recommended first version:

- keeps the app off the public internet
- works well with the current SQLite plus local file-attachment setup
- gets you iPad / phone access without a full cloud migration

### On the host PC

1. Leave the app in its current folder on the always-on Windows machine you want to host from.
2. Install Python requirements if needed:
   `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
3. Install Tailscale on that PC and sign in.
4. Start the app with:
   `start_mobile_access.bat`

That script:

- starts the app with Waitress on `127.0.0.1:5000`
- tries to enable `tailscale serve --bg localhost:5000`
- shows the Tailscale HTTPS URL if Serve is available

### On the iPad or phone

1. Install Tailscale from the App Store or Play Store.
2. Sign into the same Tailscale network.
3. Open the HTTPS URL shown by `tailscale serve status`

### Useful Tailscale commands

- enable private access:
  `tailscale serve --bg localhost:5000`
- view the mobile-access URL:
  `tailscale serve status`
- turn it off:
  `tailscale serve reset`

### Important note

This is good for private company use, but it is not yet the best long-term public-hosted setup. The app still uses:

- SQLite at `instance/shopflow.db`
- local file uploads in `instance/job_attachments`

For broader production deployment later, the next step is moving to PostgreSQL plus persistent hosted storage.

## Stress testing

The repo now includes a realistic Bath Fitters stress harness that runs against an isolated temporary SQLite database, so it does not touch the live app data.

Typical runs:

- Quick validation:
  `.\.venv\Scripts\python.exe stress_test.py --scale smoke`
- Realistic medium run:
  `.\.venv\Scripts\python.exe stress_test.py`
- Larger run:
  `.\.venv\Scripts\python.exe stress_test.py --scale large`

The harness writes:

- `stress_test_report.json`
- `stress_test_report.md`

It covers:

- concurrent dashboard, inventory, jobs, PO, receiving, and insights activity
- race-condition checks on the same inventory item, PO, job, and part record
- integrity checks for stock, duplicates, receiving accuracy, and bootstrap consistency
- AI Insights timing when `OPENAI_API_KEY` is configured

## Login and roles

Phase 1 now includes a role-based login system.

Roles:

- `manager`: full app access, admin features, job assignment and reassignment
- `installer`: assigned jobs only
- `service_tech`: assigned jobs only

Default demo users:

- `manager`
- `dal.install`
- `dal.service`
- `chi.install`
- `chi.service`
- `phx.install`
- `phx.service`

Default password for all seeded users:

- `55555`

### AI Insights setup

AI Insights uses the OpenAI API.

The launcher now looks for an API key in this file:
`.openai_api_key`

There is also a starter example file:
`.openai_api_key.example`

To enable AI Insights during normal app startup:
1. Create a file named `.openai_api_key` in the app folder
2. Paste your OpenAI API key into that file
3. Save it
4. Start the app with `start_app.bat` or your desktop shortcut

If the key file is missing, the app still opens normally, but AI Insights will stay unavailable.

The SQLite database is created automatically at `instance/shopflow.db`.

## Temporary Vercel beta

This repo can be imported into Vercel for a free temporary beta URL. Vercel provides a free `.vercel.app` URL, so no paid custom domain is required.

Vercel setup:

1. Push the latest code to GitHub.
2. In Vercel, choose **Add New > Project** and import `8gf7tvwj9d-cyber/Bath-Fitters-App`.
3. Use the default branch `main`.
4. Add the environment variables below.
5. Deploy.

Vercel will install Python dependencies from `requirements.txt`. The app entrypoint is `app.py`, and the top-level Flask variable is `app`.

Environment variables for Vercel:

- `SHOPFLOW_SECRET_KEY`: required; use a long random value for session security.
- `NEXT_PUBLIC_FEEDBACK_URL`: optional but recommended; Google Form or Google Sheet feedback link.
- `OPENAI_API_KEY`: optional; only needed for AI Insights.

Data note for this temporary beta:

- Local test data in `instance/shopflow.db` is not deleted and is still ignored by git.
- Vercel uses temporary serverless storage for this SQLite beta, so online tester changes should be treated as disposable.
- For a durable shared production version, move the database to hosted persistent storage before relying on live data.

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
