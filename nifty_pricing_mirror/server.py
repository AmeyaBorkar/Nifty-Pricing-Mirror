"""HTTP dashboard server.

Holds the most recent ``IndexSnapshot`` in memory under a lock, exposes it as
JSON at ``/api/snapshot``, and serves a static HTML/CSS/JS dashboard that
polls the endpoint. Designed to run in a daemon thread alongside the live
snapshot loop so a single CLI invocation gives both terminal output and a
web view.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from werkzeug.serving import make_server

from .pricing import IndexSnapshot

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


class DashboardServer:
    """Threaded Flask server with a single mutable snapshot slot."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self._snapshot_payload: dict | None = None
        self._lock = threading.Lock()
        self._server = None
        self._thread: threading.Thread | None = None
        self._app = self._build_app()

    # ----------------------------------------------------------------- public
    def update(self, snapshot: IndexSnapshot) -> None:
        """Replace the served snapshot. Called from the snapshot loop."""

        payload = _serialise(snapshot)
        with self._lock:
            self._snapshot_payload = payload

    def start(self) -> None:
        """Spin up the Werkzeug server in a daemon thread."""

        self._server = make_server(self.host, self.port, self._app, threaded=True)
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="dashboard", daemon=True
        )
        self._thread.start()
        log.info("Dashboard listening on http://%s:%s", self.host, self.port)

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    # ------------------------------------------------------------- internals
    def _build_app(self) -> Flask:
        app = Flask(__name__, static_folder=None)

        @app.get("/")
        def index():
            return send_from_directory(STATIC_DIR, "index.html")

        @app.get("/static/<path:filename>")
        def static_assets(filename: str):
            return send_from_directory(STATIC_DIR, filename)

        @app.get("/api/snapshot")
        def api_snapshot():
            with self._lock:
                payload = self._snapshot_payload
            if payload is None:
                return jsonify({"status": "warming_up"}), 503
            return jsonify(payload)

        @app.get("/api/health")
        def api_health():
            with self._lock:
                ready = self._snapshot_payload is not None
            return jsonify({"ready": ready})

        return app


def _serialise(snapshot: IndexSnapshot) -> dict:
    return {
        "timestamp": snapshot.timestamp.isoformat(timespec="seconds"),
        "totals": {
            "total": snapshot.total,
            "premium": snapshot.premium_count,
            "discount": snapshot.discount_count,
            "flat": snapshot.flat_count,
            "missing": snapshot.missing_count,
        },
        "averages": {
            "basis_pct": snapshot.avg_basis_pct,
            "annualised_pct": snapshot.avg_annualised_pct,
        },
        "bias": _index_bias(snapshot),
        "rows": [
            {
                "rank": idx,
                "symbol": row.symbol,
                "spot": row.spot,
                "future": row.future,
                "futures_symbol": row.futures_symbol,
                "expiry": row.expiry.isoformat() if row.expiry else None,
                "days_to_expiry": row.days_to_expiry,
                "basis": row.basis,
                "basis_pct": row.basis_pct,
                "annualised_pct": row.annualised_pct,
                "stance": row.stance.value,
            }
            for idx, row in enumerate(snapshot.rows, start=1)
        ],
    }


def _index_bias(snapshot: IndexSnapshot) -> str:
    p, d = snapshot.premium_count, snapshot.discount_count
    if p == 0 and d == 0:
        return "UNKNOWN"
    if p > d * 1.5:
        return "CONTANGO"
    if d > p * 1.5:
        return "BACKWARDATION"
    return "MIXED"
