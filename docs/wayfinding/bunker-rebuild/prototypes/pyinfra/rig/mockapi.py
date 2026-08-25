#!/usr/bin/env python3
"""Offline stand-ins for healthchecks.io and Hark.

POST /api/v3/checks/  -> 201 first time for a slug, 200 afterwards (matches the
                         real API's `unique` behaviour, which the alerting role
                         keys idempotency off).
GET  /ping/<slug>[...] -> 200, appended to the log.
POST /hark             -> 200, body appended to the log.
GET  /_log             -> newline-delimited JSON of everything received.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

LOG = Path("/var/log/mockapi.jsonl")
CHECKS = Path("/var/lib/mockapi-checks.json")
PORT = 8099


def known() -> dict[str, dict]:
    if CHECKS.exists():
        return json.loads(CHECKS.read_text())
    return {}


def record(kind: str, path: str, body: str) -> None:
    with LOG.open("a") as fh:
        fh.write(json.dumps({"kind": kind, "path": path, "body": body}) + "\n")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: object) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode()
        if self.path.startswith("/api/v3/checks"):
            payload = json.loads(body or "{}")
            slug = payload.get("slug") or payload.get("name")
            checks = known()
            fresh = slug not in checks
            record_data = {
                "name": payload.get("name", slug),
                "slug": slug,
                "schedule": payload.get("schedule"),
                "tz": payload.get("tz"),
                "grace": payload.get("grace"),
                "ping_url": f"http://127.0.0.1:{PORT}/ping/{slug}",
            }
            checks[slug] = record_data
            CHECKS.write_text(json.dumps(checks))
            record("check", self.path, body)
            self._send(201 if fresh else 200, record_data)
            return
        record("hark" if "hark" in self.path else "post", self.path, body)
        self._send(200, {"ok": True})

    def do_GET(self) -> None:
        if self.path.startswith("/api/v3/checks"):
            # The real Management API's list endpoint, which pyinfra's custom
            # fact reads to decide whether a POST is needed at all.
            self._send(200, {"checks": list(known().values())})
            return
        if self.path == "/_log":
            raw = LOG.read_bytes() if LOG.exists() else b""
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        record("ping", self.path, "")
        self._send(200, {"ok": True})

    def log_message(self, *args: object) -> None:
        pass


if __name__ == "__main__":
    LOG.touch()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
