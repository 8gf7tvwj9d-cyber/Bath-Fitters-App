# Bath Fitters Stress Test Plan

This plan matches the practical stress harness in [stress_test.py](/C:/Users/blief/Desktop/Bath Fitters App/stress_test.py).

## Purpose

Test whether the app stays fast, accurate, and stable under realistic daily load across:

- inventory search and updates
- job pulling and editing
- purchase-order creation, status changes, and partial receiving
- dashboard and insights loading while writes are happening
- AI Insights requests when `OPENAI_API_KEY` is configured

## Dataset presets

The harness uses an isolated temporary SQLite database so it does not touch the live app database.

### `medium` default

- 4 warehouses
- 3,200 parts
- 80 vendors
- 900 active jobs
- 4,500 completed jobs
- 320 open purchase orders
- 220 historical received purchase orders
- stocked and non-stock items
- seeded usage logs, receiving logs, reorder history, and job-part requirements

### `large`

- 5 warehouses
- 4,800 parts
- 120 vendors
- 1,500 active jobs
- 8,000 completed jobs
- 700 open purchase orders

### `smoke`

- smaller validation run for quick checks while developing

## Scenarios

### Morning Rush

Simulates many users loading the dashboard, searching inventory, pulling parts, editing jobs, and loading insights at the same time.

### Large Receiving Session

Focuses on repeated partial receiving, PO status changes, and per-line visual verification behavior.

### Heavy Job Pulling

Pushes job-part pulls and job updates during warehouse-heavy activity.

### Dashboard + Insights During Updates

Loads dashboard and insights while pulls, receiving, and edits happen in parallel. If AI is configured, this also includes AI Insights queries.

### End of Day Closeout

Completes ready jobs, edits records, and reloads dashboard state while archive history is changing.

### Race-condition checks

Dedicated concurrency tests cover:

- pulling the same inventory item at the same time
- receiving the same PO line at the same time
- editing the same job at the same time
- editing the same part quantity at the same time

These checks look for:

- negative stock
- over-receipts
- silent overwrite behavior
- data corruption

## Integrity checks

After the scenarios finish, the harness verifies:

- no negative stock
- no duplicate part numbers within a warehouse
- no duplicate scan codes within a warehouse
- no duplicate PO numbers
- no orphan job-part requirements
- receiving log totals stay consistent with PO line totals
- per-line visual verification stays isolated
- dashboard/bootstrap counts still match database counts

## Performance targets

- inventory search: under 2 seconds
- edit/save actions: under 2 seconds
- dashboard load: under 3 seconds
- insights load: under 5 seconds
- AI Insights: under 10 seconds

## Output

The harness writes:

- [stress_test_report.json](/C:/Users/blief/Desktop/Bath Fitters App/stress_test_report.json)
- [stress_test_report.md](/C:/Users/blief/Desktop/Bath Fitters App/stress_test_report.md)

The report includes:

- dataset summary
- pass/fail by scenario
- timing by action type
- integrity findings
- bottlenecks
- optimization recommendations

## How to run

Realistic default run:

```powershell
.\.venv\Scripts\python.exe stress_test.py
```

Quick validation run:

```powershell
.\.venv\Scripts\python.exe stress_test.py --scale smoke
```

Larger run:

```powershell
.\.venv\Scripts\python.exe stress_test.py --scale large
```
