from __future__ import annotations

import os

from waitress import serve

from app import app, init_db


def main() -> None:
    init_db()
    host = os.environ.get("SHOPFLOW_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.environ.get("SHOPFLOW_PORT", "5000") or 5000)
    threads = int(os.environ.get("SHOPFLOW_THREADS", "8") or 8)
    serve(app, host=host, port=port, threads=threads)


if __name__ == "__main__":
    main()
