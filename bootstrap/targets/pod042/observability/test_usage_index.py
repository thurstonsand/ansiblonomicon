from datetime import datetime
from pathlib import Path
import tempfile
from typing import Any, cast
import unittest
from zoneinfo import ZoneInfo

from usage_index import Days, Entry, Index, Json, Release, Views

ZONE = ZoneInfo("America/New_York")
INBOX_ZERO = "81d13a717ce9067b297422704526f6c3daf0cd566f4626fc84e43716a1f22729"
BASE = int(datetime(2026, 10, 29, 10, tzinfo=ZONE).timestamp())


def bridge(
    request: str,
    offset: int,
    reason: str,
    usage: tuple[int, int, int, int] | None,
    outcome: str = "success",
    version: str | None = None,
) -> Entry:
    record: dict[str, Json] = {
        "event": "request_complete",
        "requestId": request,
        "threadId": "T-thread",
        "requestKind": "keyed",
        "servedModel": "claude-opus-5-5",
        "outcome": outcome,
        "reason": reason,
        "changedConfigurationFields": [],
        "usage": None
        if usage is None
        else dict(
            zip(("input", "cache_read", "cache_creation", "output"), usage, strict=True)
        ),
    }
    if version is not None:
        record["version"] = version
    return (BASE + offset) * 10**9, "doppelclaude", record


IDLE_CLOSE: Entry = (
    (BASE + 3700) * 10**9,
    "doppelclaude",
    {
        "event": "runtime_close",
        "threadId": "T-thread",
        "reason": "HTTP runtime idle expiry",
    },
)
FIRST = bridge("r1", 0, "first_request", (2, 0, 1000, 10))
CONTINUED = bridge("r2", 60, "compatible", (2, 1000, 50, 10))
REOPENED = bridge("r3", 7860, "new_context", (2, 0, 1100, 10))
FAILED = bridge("r4", 7920, "compatible", None, outcome="error")
PROXY: list[Entry] = [
    (
        (BASE + 100) * 10**9,
        "cli-proxy-api",
        {
            "event": "usage",
            "event_id": "cpa:1",
            "outcome": "success",
            "model": "claude-sonnet-5-5",
            "client_key_hash": INBOX_ZERO,
            "usage": {"input": 3, "cache_read": 0, "cache_creation": 500, "output": 20},
        },
    ),
    (
        (BASE + 200) * 10**9,
        "cli-proxy-api",
        {
            "event": "usage",
            "event_id": "cpa:2",
            "outcome": "success",
            "model": "claude-sonnet-5-5",
            "client_key_hash": "shared",
            "accounting_quality": "unavailable",
            "usage": None,
        },
    ),
]


DAY = Days("2026-10-29", "2026-10-29")


class UsageIndexTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "index.sqlite3"
        self.index = Index(self.path, ZONE, frozenset({INBOX_ZERO}))

    def tearDown(self) -> None:
        self.index.db.close()
        self.directory.cleanup()

    def view(
        self, a: Days | Release = DAY, b: Days | Release | None = DAY
    ) -> dict[str, Any]:
        views = Views(self.path, ZONE)
        try:
            return cast(dict[str, Any], views.view(a, b, None))
        finally:
            views.close()

    def conversation(self) -> dict[str, Any]:
        views = Views(self.path, ZONE)
        try:
            return cast(
                dict[str, Any], views.conversation("T-thread", "2026-10-29", None)
            )
        finally:
            views.close()

    def requests(self) -> list[list[Any]]:
        return cast(list[list[Any]], self.conversation()["rows"])

    def test_separates_rewrites_from_expected_writes_and_keeps_unknown_usage(
        self,
    ) -> None:
        self.index.ingest([FIRST, CONTINUED, IDLE_CLOSE, REOPENED, FAILED, *PROXY])
        view = self.view()
        # n, unknown, errors, uncached, read, written, output, rewritten, cold
        self.assertEqual(
            view["lanes"]["amp"]["a"], [4, 1, 1, 6, 1000, 2150, 30, 1100, 1]
        )
        self.assertEqual(
            view["lanes"]["inbox_zero"]["a"], [1, 0, 0, 3, 0, 500, 20, 0, 0]
        )
        self.assertEqual(view["lanes"]["cpa_shared"]["a"], [1, 1, 0, 0, 0, 0, 0, 0, 0])
        # CLIProxyAPI cannot say why it wrote, so its writes carry no cause at all.
        self.assertEqual(view["lanes"]["inbox_zero"]["causes"], {})
        self.assertEqual(
            {row[0]: row[11] for row in view["consumers"]}["inbox_zero"], {}
        )
        self.assertEqual(view["gaps"]["a"], [[7800.0, "amp"]])
        self.assertEqual(
            [row[1:4] + row[7:10] for row in self.requests()],
            [
                ["first_request", "success", 2, None, None, None],
                ["compatible", "success", 2, 0, 60.0, None],
                ["new_context", "success", 2, 1, 7800.0, "HTTP runtime idle expiry"],
                ["compatible", "error", None, None, 60.0, None],
            ],
        )

    def test_late_records_reannotate_the_thread_and_repeats_change_nothing(
        self,
    ) -> None:
        self.index.ingest([FIRST, REOPENED])
        self.assertEqual(self.requests()[1][7:10], [1, 7860.0, None])
        self.index.ingest([CONTINUED])
        self.assertEqual(self.requests()[2][7:10], [1, 7800.0, None])
        self.index.ingest([IDLE_CLOSE])
        self.index.ingest([FIRST, CONTINUED, IDLE_CLOSE, REOPENED])
        self.assertEqual(
            [row[7:10] for row in self.requests()],
            [
                [None, None, None],
                [0, 60.0, None],
                [1, 7800.0, "HTTP runtime idle expiry"],
            ],
        )
        self.assertEqual(
            self.view()["lanes"]["amp"]["a"], [3, 0, 0, 6, 1000, 2150, 30, 1100, 1]
        )

    def test_compares_a_release_with_the_one_before_it(self) -> None:
        self.index.ingest(
            [
                bridge("r1", 0, "first_request", (2, 0, 1000, 10), version="0.14.15"),
                bridge("r2", 60, "compatible", (2, 1000, 50, 10), version="0.14.15"),
                bridge("r3", 7860, "new_context", (2, 0, 1100, 10), version="0.14.16"),
                *PROXY,
            ]
        )
        view = self.view(Release("0.14.16"), None)
        self.assertEqual(view["b"]["id"], "v:0.14.15")
        self.assertEqual(view["a"]["span"], [BASE + 7860, BASE + 7860])
        self.assertEqual(view["lanes"]["amp"]["a"], [1, 0, 0, 2, 0, 1100, 10, 1100, 1])
        self.assertEqual(view["lanes"]["amp"]["b"], [2, 0, 0, 4, 1000, 1050, 20, 0, 0])
        self.assertNotIn("inbox_zero", view["lanes"])
        self.assertEqual(
            view["releases"],
            [["0.14.15", BASE, BASE + 60], ["0.14.16", BASE + 7860, BASE + 7860]],
        )

    def test_schema_change_rebuilds_from_loki_but_keeps_notes_and_titles(
        self,
    ) -> None:
        self.index.ingest([FIRST])
        views = Views(self.path, ZONE)
        views.add_note({"start": BASE, "end": BASE + 60, "text": "Ran out"})
        views.add_titles({"T-thread": "Cache hunt"})
        views.close()
        self.assertEqual(self.conversation()["title"], "Cache hunt")
        with self.index.db:
            self.index.db.execute("UPDATE meta SET value = 1 WHERE key = 'schema'")
        self.index.db.close()
        self.index = Index(self.path, ZONE, frozenset({INBOX_ZERO}))
        self.assertIsNone(self.index.cursor())
        self.assertEqual(self.view()["empty"], True)
        self.index.ingest([FIRST])
        view = self.view()
        self.assertEqual([note[3] for note in view["notes"]], ["Ran out"])
        self.assertEqual(view["titles"], {"T-thread": "Cache hunt"})


if __name__ == "__main__":
    unittest.main()
