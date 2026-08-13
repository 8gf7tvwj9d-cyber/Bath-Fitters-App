from __future__ import annotations

import os

from waitress import serve

# Importing app.py already initializes the database. server.py then performs the
# one-time Office 93 cleanup and rebuilds the real catalog, so do not initialize
# a second time after that conversion has completed.
from server import app


def main() -> None:
    host = os.environ.get("SHOPFLOW_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.environ.get("SHOPFLOW_PORT", "5000") or 5000)
    threads = int(os.environ.get("SHOPFLOW_THREADS", "8") or 8)
    serve(app, host=host, port=port, threads=threads)


if __name__ == "__main__":
    main()
