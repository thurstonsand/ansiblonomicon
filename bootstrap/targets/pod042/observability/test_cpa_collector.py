from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
from typing import cast
import unittest

from cpa_collector import Json


def usage_record(execution: str = "execution-1") -> dict[str, Json]:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "execution_id": execution,
        "request_id": "request-1",
        "session_id": "session-1",
        "provider": "claude",
        "model": "claude-sonnet-5-5",
        "response_model": "claude-sonnet-5-5",
        "api_key": "client-secret-do-not-store",
        "access_token_sha256": "credential-material-do-not-store",
        "response_headers": {"Authorization": ["upstream-secret-do-not-store"]},
        "fail": {"status_code": 200, "body": "private-email-do-not-store"},
        "failed": False,
        "latency_ms": 147,
        "token_breakdown": {
            "schema_version": 2,
            "quality": "complete",
            "total_tokens": 127,
            "input": {
                "total_tokens": 100,
                "uncached_tokens": 3,
                "cache_read_tokens": 80,
                "cache_write_tokens": 17,
            },
            "output": {
                "total_tokens": 27,
                "reasoning_tokens": 7,
                "non_reasoning_tokens": 20,
            },
            "unclassified_tokens": 0,
        },
    }


class QueueServer(ThreadingHTTPServer):
    payload: list[Json]
    status: int = 200
    requests: int = 0
    authorized: bool = False

    def __init__(self, host: str, port: int, payload: list[Json]) -> None:
        super().__init__((host, port), QueueHandler)
        self.payload = payload


class QueueHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        server = cast(QueueServer, self.server)
        server.requests += 1
        server.authorized = self.headers.get("Authorization") == "Bearer fixture-key"
        self.send_response(server.status)
        if server.status == 302:
            self.send_header("Location", "/must-not-follow")
        self.end_headers()
        payload = server.payload
        server.payload = []
        self.wfile.write(json.dumps(payload).encode())

    def do_POST(self) -> None:
        cast(QueueServer, self.server).payload.append(usage_record("execution-2"))
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


class CollectionTests(unittest.TestCase):
    def collect(
        self, payload: list[Json], status: int = 200, *, full_spool: bool = False
    ) -> tuple[subprocess.CompletedProcess[str], list[dict[str, Json]], str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "key").write_text("fixture-key")
            if full_spool:
                with (root / "records.jsonl").open("w") as stream:
                    stream.write('{"event":"older"}\n')
                    stream.truncate(64 * 1024 * 1024)
            with QueueServer("127.0.0.1", 0, payload) as server:
                server.status = status
                thread = Thread(target=server.serve_forever)
                thread.start()
                try:
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(Path(__file__).with_name("cpa_collector.py")),
                            "--url",
                            f"http://127.0.0.1:{server.server_port}/usage?count=1000",
                            "--key-file",
                            str(root / "key"),
                            "--output",
                            str(root / "records.jsonl"),
                            "--once",
                        ],
                        text=True,
                        capture_output=True,
                        timeout=10,
                    )
                finally:
                    server.shutdown()
                    thread.join()
                self.assertEqual(server.requests, 1)
                self.assertTrue(server.authorized)
            spool = root / "records.jsonl"
            self.assertEqual(spool.stat().st_mode & 0o777, 0o600)
            if full_spool:
                archived = root / "records.jsonl.1"
                self.assertEqual(archived.stat().st_size, 64 * 1024 * 1024)
                with archived.open() as stream:
                    self.assertEqual(stream.readline(), '{"event":"older"}\n')
            text = spool.read_text()
            records = [
                cast(dict[str, Json], json.loads(line)) for line in text.splitlines()
            ]
            return result, records, text

    def test_rotates_and_persists_nonoverlapping_usage_without_secrets(self) -> None:
        result, records, text = self.collect([usage_record()], full_spool=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        usage = next(row for row in records if row["event"] == "usage")
        self.assertEqual(usage["event_id"], "cpa:execution-1")
        self.assertEqual(
            usage["usage"],
            {"input": 3, "cache_read": 80, "cache_creation": 17, "output": 27},
        )
        self.assertEqual(usage["reasoning_tokens"], 7)
        self.assertEqual(
            usage["client_key_hash"],
            "cf34a2eb493fbdc86411c3b8807b71e601d9739056fd60f36b0f3d2f38a7d2c5",
        )
        self.assertNotIn("do-not-store", text + result.stderr + result.stdout)
        self.assertEqual(usage["session_id"], "session-1")

    def test_unknown_accounting_and_failure_are_not_zero_usage(self) -> None:
        record = usage_record()
        record["token_breakdown"] = {"schema_version": 99}
        record["failed"] = True
        partial = usage_record("partial")
        breakdown = cast(dict[str, Json], partial["token_breakdown"])
        breakdown.update(
            quality="unclassified",
            total_tokens=136,
            unclassified_tokens=9,
            extra="secret-do-not-store",
        )
        result, records, text = self.collect([record, partial])
        self.assertEqual(result.returncode, 0, result.stderr)
        usage = next(row for row in records if row["event"] == "usage")
        self.assertIsNone(usage["usage"])
        self.assertEqual(usage["accounting_quality"], "unavailable")
        self.assertEqual(usage["outcome"], "error")
        observed = next(row for row in records if row["event_id"] == "cpa:partial")
        self.assertIsNone(observed["usage"])
        self.assertEqual(
            observed["token_breakdown"],
            {
                "schema_version": 2,
                "quality": "unclassified",
                "total_tokens": 136,
                "input": {
                    "total_tokens": 100,
                    "uncached_tokens": 3,
                    "cache_read_tokens": 80,
                    "cache_write_tokens": 17,
                },
                "output": {
                    "total_tokens": 27,
                    "non_reasoning_tokens": 20,
                    "reasoning_tokens": 7,
                },
                "unclassified_tokens": 9,
            },
        )
        self.assertNotIn("do-not-store", text)

    def test_bad_accounting_preserves_valid_peers_and_reports_gap(self) -> None:
        invalid = usage_record("bad")
        cast(dict[str, Json], invalid["token_breakdown"])["total_tokens"] = 128
        result, records, text = self.collect([invalid, usage_record("good")])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            [r["event_id"] for r in records if r["event"] == "usage"], ["cpa:good"]
        )
        gap = next(row for row in records if row["event"] == "collector_rejected")
        self.assertEqual(gap["records"], 1)
        self.assertNotIn("do-not-store", text + result.stderr)

    def test_http_failures_never_follow_redirects_or_log_bodies(self) -> None:
        for status in (302, 403, 503):
            with self.subTest(status=status):
                result, records, text = self.collect(["secret-response-body"], status)
                self.assertEqual(result.returncode, 1)
                error = next(
                    row for row in records if row["event"] == "collector_error"
                )
                self.assertEqual(error["http_status"], status)
                self.assertNotIn("secret-response-body", text + result.stderr)


if __name__ == "__main__":
    if "--serve" in sys.argv:
        with QueueServer("0.0.0.0", 8317, [usage_record()]) as queue:
            queue.serve_forever()
    else:
        unittest.main()
