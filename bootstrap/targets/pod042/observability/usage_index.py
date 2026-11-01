#!/usr/bin/env python3
"""Index Loki's usage records into SQLite rollups and serve the cache usage page."""

import argparse
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import gzip
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import batched
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
import traceback
from typing import cast
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen
from zoneinfo import ZoneInfo

type Json = bool | int | float | str | list[Json] | dict[str, Json] | None
type Usage = tuple[int, int, int, int]

BUCKETS = ("input", "cache_read", "cache_creation", "output")
REQUEST_KINDS = {
    "keyed": "amp",
    "opencode": "opencode",
    "opencode_one_shot": "opencode",
    "derived": "derived",
    "anonymous": "anonymous",
}
REASONS = (
    "compatible",
    "first_request",
    "new_context",
    "history_diverged",
    "previous_request_failed",
)
# Writes that replace context the cache already held; new turns and first requests are expected.
REWRITE_CAUSES = (
    "new_context",
    "config",
    "history_diverged",
    "previous_request_failed",
)
REWRITTEN = (
    "CASE WHEN cause IN ("
    + ",".join(f"'{cause}'" for cause in REWRITE_CAUSES)
    + ") THEN cache_creation ELSE 0 END"
)
TOTALS = (
    "sum(n), sum(unknown), sum(errors), sum(input), sum(cache_read),"
    f" sum(cache_creation), sum(output), sum({REWRITTEN}), sum(cold)"
)
LOKI_QUERY = '{service_name=~"doppelclaude|cli-proxy-api"}'
LOKI_LIMIT = 5000
LOKI_SPAN_NS = 30 * 86400 * 10**9
OVERLAP_NS = 3600 * 10**9
RESCAN_NS = 2 * 86400 * 10**9
RESCAN_SECONDS = 3600
CONVERSATION_LIMIT = 2000
TITLE_LIMIT = 2 * 1024 * 1024
# Bump when a change alters what the index derives; everything but notes and titles
# is rebuilt from Loki.
SCHEMA_VERSION = 2
DERIVED_TABLES = (
    "request",
    "runtime_close",
    "startup",
    "coverage",
    "day_rollup",
    "hour_rollup",
    "release",
    "meta",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS request (
  key TEXT PRIMARY KEY, t REAL NOT NULL, day TEXT NOT NULL, hour INTEGER NOT NULL,
  source TEXT NOT NULL, consumer TEXT NOT NULL, thread TEXT, model TEXT NOT NULL,
  cause TEXT, outcome TEXT NOT NULL, version TEXT,
  input INTEGER, cache_read INTEGER, cache_creation INTEGER, output INTEGER,
  detail TEXT NOT NULL, gap REAL, cold INTEGER, closed_by TEXT
);
CREATE INDEX IF NOT EXISTS request_day ON request (day);
CREATE INDEX IF NOT EXISTS request_thread ON request (thread, t);
CREATE INDEX IF NOT EXISTS request_consumer ON request (consumer, t);
CREATE INDEX IF NOT EXISTS request_version ON request (version, t);
CREATE INDEX IF NOT EXISTS request_cold_reopen ON request (day)
  WHERE cause = 'new_context' AND cold = 1;
CREATE TABLE IF NOT EXISTS runtime_close (
  thread TEXT NOT NULL, t REAL NOT NULL, reason TEXT NOT NULL,
  PRIMARY KEY (thread, t, reason)
);
CREATE TABLE IF NOT EXISTS startup (t REAL PRIMARY KEY);
CREATE TABLE IF NOT EXISTS coverage (key TEXT PRIMARY KEY, t REAL NOT NULL, kind TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS day_rollup (
  day TEXT NOT NULL, source TEXT NOT NULL, consumer TEXT NOT NULL, model TEXT NOT NULL,
  cause TEXT, version TEXT, n INTEGER NOT NULL, unknown INTEGER NOT NULL,
  errors INTEGER NOT NULL, input INTEGER NOT NULL, cache_read INTEGER NOT NULL,
  cache_creation INTEGER NOT NULL, output INTEGER NOT NULL, cold INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS day_rollup_day ON day_rollup (day);
CREATE INDEX IF NOT EXISTS day_rollup_version ON day_rollup (version);
CREATE TABLE IF NOT EXISTS hour_rollup (
  hour INTEGER NOT NULL, day TEXT NOT NULL, source TEXT NOT NULL, model TEXT NOT NULL,
  n INTEGER NOT NULL, unknown INTEGER NOT NULL,
  input INTEGER NOT NULL, cache_read INTEGER NOT NULL, cache_creation INTEGER NOT NULL,
  PRIMARY KEY (hour, source, model)
);
CREATE INDEX IF NOT EXISTS hour_rollup_day ON hour_rollup (day);
CREATE TABLE IF NOT EXISTS note (
  id INTEGER PRIMARY KEY, start REAL NOT NULL, end REAL NOT NULL, text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS release (
  version TEXT PRIMARY KEY, first REAL NOT NULL, last REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS title (id TEXT PRIMARY KEY, title TEXT NOT NULL);
"""
META = "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL)"


@dataclass(frozen=True)
class Days:
    first: str
    last: str


@dataclass(frozen=True)
class Release:
    version: str


type Window = Days | Release


def local_day(t: float, zone: ZoneInfo) -> str:
    return datetime.fromtimestamp(t, zone).date().isoformat()


def object_value(value: Json) -> dict[str, Json]:
    if not isinstance(value, dict):
        raise ValueError("expected object")
    return value


def text_value(value: Json) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("expected nonempty string")
    return value


def optional_text(value: Json) -> str | None:
    return None if value is None else text_value(value)


def count_value(value: Json) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("expected nonnegative integer")
    return value


def usage_value(value: Json) -> Usage | None:
    """Usage the source could not account for stays unknown, never zero."""
    if value is None:
        return None
    buckets = object_value(value)
    counts = [buckets.get(bucket) for bucket in BUCKETS]
    if all(count is None for count in counts):
        return None
    return cast(Usage, tuple(count_value(count) for count in counts))


@dataclass(frozen=True)
class Request:
    key: str
    t: float
    source: str
    consumer: str
    thread: str | None
    model: str
    # CLIProxyAPI cannot know why a cache write happened, so its requests have no cause.
    cause: str | None
    outcome: str
    version: str | None
    usage: Usage | None
    detail: dict[str, Json]


def bridge_request(record: dict[str, Json], t: float) -> Request:
    kind = record.get("requestKind")
    source = "unlabelled" if kind is None else REQUEST_KINDS[text_value(kind)]
    thread = optional_text(record.get("threadId"))
    changed = record.get("changedConfigurationFields") or []
    if not isinstance(changed, list):
        raise ValueError("changedConfigurationFields must be a list")
    reason = optional_text(record.get("reason"))
    if reason is not None and reason not in REASONS:
        raise ValueError(f"unclassified bridge reason {reason}")
    created: dict[str, Json] = {}
    for execution in cast(list[Json], record.get("executions") or []):
        if object_value(execution).get("event") == "query_created":
            created = object_value(execution)
            break
    rebuild = created.get("rebuild")
    detail: dict[str, Json] = {
        "sync": record.get("sync"),
        "lane": record.get("lane"),
        "context": None
        if rebuild is None
        else object_value(rebuild).get("contextSource"),
        "forced": created.get("forcedCause"),
        "changed": changed,
        "messages": record.get("messageCount"),
        "duration_ms": record.get("durationMs"),
        "error": record.get("errorCategory"),
        "status": record.get("httpStatus"),
    }
    return Request(
        key=text_value(record.get("requestId")),
        t=t,
        source=source,
        # Requests without a thread, such as anonymous and one-shot calls, pool by kind.
        consumer=thread or optional_text(kind) or source,
        thread=thread,
        model=optional_text(record.get("servedModel")) or "unknown",
        cause="config" if changed else reason or "unrecorded",
        outcome=text_value(record.get("outcome")),
        version=optional_text(record.get("version")),
        usage=usage_value(record.get("usage")),
        detail={key: value for key, value in detail.items() if value not in (None, [])},
    )


def proxy_request(
    record: dict[str, Json], t: float, inbox_zero: frozenset[str]
) -> Request:
    source = (
        "inbox_zero" if record.get("client_key_hash") in inbox_zero else "cpa_shared"
    )
    detail: dict[str, Json] = {
        "latency_ms": record.get("latency_ms"),
        "ttft_ms": record.get("ttft_ms"),
        "status": record.get("http_status"),
        "accounting": record.get("accounting_quality"),
    }
    return Request(
        key=text_value(record.get("event_id")),
        t=t,
        source=source,
        consumer=source,
        thread=None,
        model=optional_text(record.get("model")) or "unknown",
        cause=None,
        outcome=text_value(record.get("outcome")),
        version=None,
        usage=usage_value(record.get("usage")),
        detail={key: value for key, value in detail.items() if value is not None},
    )


type Entry = tuple[int, str, dict[str, Json]]


class Index:
    """Single writer: inserts records, annotates thread chains, and rebuilds touched days."""

    def __init__(self, path: Path, zone: ZoneInfo, inbox_zero: frozenset[str]) -> None:
        self.db = connect(path)
        self.db.execute(META)
        if self.meta("schema") != SCHEMA_VERSION:
            with self.db:
                for table in DERIVED_TABLES:
                    self.db.execute(f"DROP TABLE IF EXISTS {table}")
                self.db.execute(META)
                self.db.execute(
                    "INSERT INTO meta VALUES ('schema', ?)", (SCHEMA_VERSION,)
                )
        self.db.executescript(SCHEMA)
        self.zone = zone
        self.inbox_zero = inbox_zero

    def meta(self, key: str) -> int | None:
        row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else cast(int, row[0])

    def cursor(self) -> int | None:
        return self.meta("cursor")

    def ingest(self, entries: Sequence[Entry]) -> None:
        if not entries:
            return
        touched: dict[str, float] = {}
        restarted: float | None = None
        days: set[str] = set()
        with self.db:
            for ts, service, record in entries:
                t = ts / 1e9
                event = record.get("event")
                if service == "doppelclaude" and event == "request_complete":
                    request = bridge_request(record, t)
                elif service == "cli-proxy-api" and event == "usage":
                    request = proxy_request(record, t, self.inbox_zero)
                elif service == "doppelclaude" and event == "runtime_close":
                    # Anonymous runtimes close without a thread; they have no chain to annotate.
                    thread = optional_text(record.get("threadId"))
                    if (
                        thread is not None
                        and self.db.execute(
                            "INSERT OR IGNORE INTO runtime_close VALUES (?, ?, ?)",
                            (thread, t, text_value(record.get("reason"))),
                        ).rowcount
                    ):
                        touched[thread] = min(touched.get(thread, t), t)
                    continue
                elif service == "doppelclaude" and event == "startup":
                    if self.db.execute(
                        "INSERT OR IGNORE INTO startup VALUES (?)", (t,)
                    ).rowcount:
                        restarted = t if restarted is None else min(restarted, t)
                    continue
                elif service == "cli-proxy-api" and event in (
                    "collector_error",
                    "collector_rejected",
                ):
                    self.db.execute(
                        "INSERT OR IGNORE INTO coverage VALUES (?, ?, ?)",
                        (
                            text_value(record.get("event_id")),
                            t,
                            text_value(record.get("coverage")),
                        ),
                    )
                    continue
                else:
                    continue
                if self.insert(request):
                    days.add(local_day(t, self.zone))
                    if request.thread is not None:
                        touched[request.thread] = min(touched.get(request.thread, t), t)
            if restarted is not None:
                since = restarted
                for (thread,) in self.db.execute(
                    "SELECT DISTINCT thread FROM request WHERE thread IS NOT NULL AND t >= ?",
                    (since,),
                ).fetchall():
                    touched[thread] = min(touched.get(thread, since), since)
            for thread, since in touched.items():
                days |= self.annotate(thread, since)
            self.roll_up(days)
            self.db.execute(
                "INSERT INTO meta VALUES ('cursor', ?) ON CONFLICT (key)"
                " DO UPDATE SET value = max(value, excluded.value)",
                (max(ts for ts, _, _ in entries),),
            )

    def insert(self, request: Request) -> bool:
        usage = request.usage or (None, None, None, None)
        if request.version is not None:
            self.db.execute(
                "INSERT INTO release VALUES (?, ?, ?) ON CONFLICT (version) DO UPDATE"
                " SET first = min(first, excluded.first), last = max(last, excluded.last)",
                (request.version, request.t, request.t),
            )
        return bool(
            self.db.execute(
                "INSERT OR IGNORE INTO request VALUES"
                " (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)",
                (
                    request.key,
                    request.t,
                    local_day(request.t, self.zone),
                    int(request.t // 3600) * 3600,
                    request.source,
                    request.consumer,
                    request.thread,
                    request.model,
                    request.cause,
                    request.outcome,
                    request.version,
                    *usage,
                    json.dumps(request.detail, separators=(",", ":")),
                ),
            ).rowcount
        )

    def annotate(self, thread: str, since: float) -> set[str]:
        """Recompute idle gap, coldness, and runtime closure from `since` onward."""
        seed = self.db.execute(
            "SELECT t, cache_read + cache_creation FROM request"
            " WHERE thread = ? AND t < ? AND input IS NOT NULL"
            " ORDER BY t DESC, key DESC LIMIT 1",
            (thread, since),
        ).fetchone()
        previous, prefix = cast(tuple[float | None, int | None], seed or (None, None))
        floor = since if previous is None else previous
        closes = self.db.execute(
            "SELECT t, reason FROM runtime_close WHERE thread = ? AND t >= ? ORDER BY t",
            (thread, floor),
        ).fetchall()
        starts = [
            row[0]
            for row in self.db.execute("SELECT t FROM startup WHERE t >= ?", (floor,))
        ]
        days: set[str] = set()
        rows = self.db.execute(
            "SELECT key, t, day, cache_read, cache_creation FROM request"
            " WHERE thread = ? AND t >= ? ORDER BY t, key",
            (thread, since),
        ).fetchall()
        for key, t, day, read, write in rows:
            gap = cold = closed = None
            if previous is not None and prefix is not None:
                gap = t - previous
                cold = None if read is None else int(read < prefix / 2)
                closed = next(
                    (reason for at, reason in reversed(closes) if previous <= at <= t),
                    None,
                )
                if closed is None and any(previous <= at <= t for at in starts):
                    closed = "HTTP server restart"
            self.db.execute(
                "UPDATE request SET gap = ?, cold = ?, closed_by = ? WHERE key = ?",
                (gap, cold, closed, key),
            )
            days.add(day)
            if read is not None:
                previous, prefix = t, read + write
        return days

    def roll_up(self, days: set[str]) -> None:
        for chunk in batched(sorted(days), 500, strict=False):
            marks = ",".join("?" * len(chunk))
            self.db.execute(f"DELETE FROM day_rollup WHERE day IN ({marks})", chunk)
            self.db.execute(
                "INSERT INTO day_rollup SELECT day, source, consumer, model, cause, version,"
                " count(*), count(*) - count(input), sum(outcome != 'success'),"
                " total(input), total(cache_read), total(cache_creation), total(output),"
                f" total(cold) FROM request WHERE day IN ({marks})"
                " GROUP BY day, source, consumer, model, cause, version",
                chunk,
            )
            self.db.execute(f"DELETE FROM hour_rollup WHERE day IN ({marks})", chunk)
            self.db.execute(
                "INSERT INTO hour_rollup SELECT hour, day, source, model,"
                " count(*), count(*) - count(input),"
                " total(input), total(cache_read), total(cache_creation)"
                f" FROM request WHERE day IN ({marks}) GROUP BY hour, day, source, model",
                chunk,
            )


def connect(path: Path) -> sqlite3.Connection:
    # The writer is built before the server starts, then handed to the indexing thread.
    db = sqlite3.connect(path, timeout=10, check_same_thread=False)
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA synchronous = NORMAL")
    return db


class Views:
    """Read side: every query reads rollups, except per-request drill-down and gaps."""

    def __init__(self, path: Path, zone: ZoneInfo) -> None:
        self.db = connect(path)
        self.zone = zone

    def close(self) -> None:
        self.db.close()

    def view(
        self, a: Window | None, b: Window | None, models: list[str] | None
    ) -> Json:
        # One read snapshot, so an ingest commit cannot land between these queries.
        self.db.execute("BEGIN")
        first, last = self.db.execute(
            "SELECT min(day), max(day) FROM day_rollup"
        ).fetchone()
        if first is None:
            return {"empty": True}
        releases = {
            version: (start, end)
            for version, start, end in self.db.execute(
                "SELECT version, first, last FROM release ORDER BY first"
            )
        }
        if a is None:
            end = date.fromisoformat(last)
            a = Days((end - timedelta(days=2)).isoformat(), last)
        a_info = self.window(a, releases)
        if b is None:
            b = self.previous(a, a_info, releases)
        b_info = self.window(b, releases)
        where, args = model_filter(models)
        lanes: dict[str, dict[str, Json]] = {}
        for name, window in (("a", a), ("b", b)):
            within, bounds = window_filter(window)
            for source, *totals in self.db.execute(
                f"SELECT source, {TOTALS} FROM day_rollup WHERE 1{within}{where}"
                " GROUP BY source",
                (*bounds, *args),
            ):
                lanes.setdefault(source, {"a": None, "b": None, "causes": {}})[name] = (
                    totals
                )
        consumers: dict[tuple[str, str], list[Json]] = {}
        within, bounds = window_filter(a)
        for source, consumer, cause, *totals in self.db.execute(
            f"SELECT source, consumer, cause, {TOTALS} FROM day_rollup"
            f" WHERE 1{within}{where} GROUP BY source, consumer, cause",
            (*bounds, *args),
        ):
            row = consumers.setdefault(
                (source, consumer), [consumer, source, *[0] * 9, {}]
            )
            for offset, value in enumerate(totals):
                row[2 + offset] = cast(int, row[2 + offset]) + value
            if cause is not None:
                causes = cast(dict[str, Json], lanes[source]["causes"])
                causes[cause] = cast(int, causes.get(cause, 0)) + totals[5]
                cast(dict[str, Json], row[11])[cause] = totals[5]
        ids = [consumer for _, consumer in consumers]
        titles = dict(
            self.db.execute(
                f"SELECT id, title FROM title WHERE id IN ({','.join('?' * len(ids))})",
                ids,
            ).fetchall()
        )
        span_days = (date.fromisoformat(last) - date.fromisoformat(first)).days + 1
        calendar = [
            [day.isoformat(), self.midnight(day)]
            for day in (
                date.fromisoformat(first) + timedelta(days=offset)
                for offset in range(span_days + 1)
            )
        ]
        if span_days <= 31:
            unit, timeline = (
                "hour",
                self.db.execute(
                    "SELECT hour, sum(n), sum(unknown), sum(input + cache_read + cache_creation),"
                    f" sum(cache_read) FROM hour_rollup WHERE 1{where} GROUP BY hour ORDER BY hour",
                    args,
                ).fetchall(),
            )
        else:
            unit, timeline = (
                "day",
                [
                    (self.midnight(date.fromisoformat(day)), *rest)
                    for day, *rest in self.db.execute(
                        "SELECT day, sum(n), sum(unknown),"
                        " sum(input + cache_read + cache_creation), sum(cache_read)"
                        f" FROM day_rollup WHERE 1{where} GROUP BY day ORDER BY day",
                        args,
                    )
                ],
            )
        return {
            "tz": self.zone.key,
            "a": a_info,
            "b": b_info,
            "calendar": cast(Json, calendar),
            "releases": [
                [version, start, end] for version, (start, end) in releases.items()
            ],
            "models": rows(
                self.db.execute(
                    "SELECT model, sum(n) FROM day_rollup GROUP BY model ORDER BY 2 DESC"
                )
            ),
            "timeline": {
                "unit": unit,
                "rows": cast(Json, [list(row) for row in timeline]),
            },
            "notes": rows(
                self.db.execute("SELECT id, start, end, text FROM note ORDER BY start")
            ),
            "coverage": rows(
                self.db.execute("SELECT t, kind FROM coverage ORDER BY t")
            ),
            "lanes": cast(Json, lanes),
            "daily": rows(
                self.db.execute(
                    "SELECT day, source, sum(input + cache_read + cache_creation),"
                    f" sum({REWRITTEN}), sum(n), sum(unknown) FROM day_rollup"
                    f" WHERE 1{where} GROUP BY day, source ORDER BY day",
                    args,
                )
            ),
            "daily_causes": rows(
                self.db.execute(
                    "SELECT day, cause, sum(cache_creation) FROM day_rollup"
                    f" WHERE cause IN ({','.join('?' * len(REWRITE_CAUSES))}){where}"
                    " GROUP BY day, cause ORDER BY day",
                    (*REWRITE_CAUSES, *args),
                )
            ),
            "consumers": cast(Json, list(consumers.values())),
            "titles": titles,
            "gaps": {
                name: rows(
                    self.db.execute(
                        "SELECT gap, source FROM request"
                        f" WHERE cause = 'new_context' AND cold = 1{within}{where}",
                        (*bounds, *args),
                    )
                )
                for name, (within, bounds) in (
                    ("a", window_filter(a)),
                    ("b", window_filter(b)),
                )
            },
        }

    def window(
        self, window: Window, releases: dict[str, tuple[float, float]]
    ) -> dict[str, Json]:
        """Whole days or one bridge release, with its days and time span for the page."""
        if isinstance(window, Days):
            end = date.fromisoformat(window.last) + timedelta(days=1)
            return {
                "id": f"{window.first}..{window.last}",
                "version": None,
                "days": [window.first, window.last],
                "span": [
                    self.midnight(date.fromisoformat(window.first)),
                    self.midnight(end),
                ],
            }
        start, end = releases[window.version]
        return {
            "id": f"v:{window.version}",
            "version": window.version,
            "days": [local_day(start, self.zone), local_day(end, self.zone)],
            "span": [start, end],
        }

    def previous(
        self,
        window: Window,
        info: dict[str, Json],
        releases: dict[str, tuple[float, float]],
    ) -> Window:
        """A release compares with the one before it; days, with as many days before."""
        if isinstance(window, Release):
            versions = list(releases)
            at = versions.index(window.version)
            if at > 0:
                return Release(versions[at - 1])
        first, last = (
            date.fromisoformat(cast(str, day)) for day in cast(list[Json], info["days"])
        )
        span = last - first + timedelta(days=1)
        return Days((first - span).isoformat(), (first - timedelta(days=1)).isoformat())

    def midnight(self, day: date) -> int:
        return int(datetime(day.year, day.month, day.day, tzinfo=self.zone).timestamp())

    def conversation(
        self, consumer: str, through: str, models: list[str] | None
    ) -> Json:
        where, args = model_filter(models)
        found = self.db.execute(
            "SELECT t, cause, outcome, input, cache_read, cache_creation, output, cold, gap,"
            f" closed_by, model, detail FROM request WHERE consumer = ? AND day <= ?{where}"
            " ORDER BY t DESC, key DESC LIMIT ?",
            (consumer, through, *args, CONVERSATION_LIMIT),
        ).fetchall()
        title = self.db.execute(
            "SELECT title FROM title WHERE id = ?", (consumer,)
        ).fetchone()
        return {
            "id": consumer,
            "title": None if title is None else title[0],
            "limited": len(found) == CONVERSATION_LIMIT,
            "rows": [[*row[:-1], json.loads(row[-1])] for row in reversed(found)],
        }

    def add_note(self, value: Json) -> None:
        note = object_value(value)
        start, end, text = note.get("start"), note.get("end"), note.get("text")
        if (
            not isinstance(start, int | float)
            or not isinstance(end, int | float)
            or end < start
        ):
            raise ValueError("note needs start <= end in epoch seconds")
        if not isinstance(text, str) or not 0 < len(text.strip()) <= 200:
            raise ValueError("note text must be 1 to 200 characters")
        with self.db:
            self.db.execute(
                "INSERT INTO note (start, end, text) VALUES (?, ?, ?)",
                (start, end, text.strip()),
            )

    def add_titles(self, value: Json) -> None:
        titles = object_value(value)
        for thread, title in titles.items():
            if not thread.startswith("T-"):
                raise ValueError(f"{thread} is not an Amp thread ID")
            text_value(title)
        with self.db:
            self.db.executemany(
                "INSERT INTO title VALUES (?, ?)"
                " ON CONFLICT (id) DO UPDATE SET title = excluded.title",
                titles.items(),
            )

    def delete_note(self, note: int) -> None:
        with self.db:
            self.db.execute("DELETE FROM note WHERE id = ?", (note,))


def rows(cursor: sqlite3.Cursor) -> Json:
    return [list(row) for row in cursor.fetchall()]


def model_filter(models: list[str] | None) -> tuple[str, tuple[str, ...]]:
    if models is None:
        return "", ()
    if not models:
        raise ValueError("select at least one model")
    return f" AND model IN ({','.join('?' * len(models))})", tuple(models)


def window_filter(window: Window) -> tuple[str, tuple[str, ...]]:
    if isinstance(window, Release):
        return " AND version = ?", (window.version,)
    return " AND day BETWEEN ? AND ?", (window.first, window.last)


def parse_window(value: str | None) -> Window | None:
    """`YYYY-MM-DD..YYYY-MM-DD` for whole days, or `v:<version>` for one bridge release."""
    if value is None:
        return None
    if value.startswith("v:"):
        return Release(text_value(value.removeprefix("v:")))
    low, high = value.split("..")
    if date.fromisoformat(low) > date.fromisoformat(high):
        raise ValueError("window must run forward")
    return Days(low, high)


class Loki:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")

    def read(self, start: int, end: int) -> Iterator[list[Entry]]:
        """Yield time-ordered pages; a page may repeat entries at its first timestamp."""
        while start < end:
            stop = min(end, start + LOKI_SPAN_NS)
            query = urlencode(
                {
                    "query": LOKI_QUERY,
                    "start": start,
                    "end": stop,
                    "limit": LOKI_LIMIT,
                    "direction": "forward",
                }
            )
            with urlopen(
                f"{self.url}/loki/api/v1/query_range?{query}", timeout=60
            ) as response:
                payload = object_value(cast(Json, json.load(response)))
            streams = cast(
                list[dict[str, Json]], object_value(payload["data"])["result"]
            )
            entries = sorted(
                (
                    (
                        int(cast(str, value[0])),
                        text_value(object_value(stream["stream"])["service_name"]),
                        object_value(cast(Json, json.loads(cast(str, value[1])))),
                    )
                    for stream in streams
                    for value in cast(list[list[Json]], stream["values"])
                ),
                key=lambda entry: entry[0],
            )
            yield entries
            if len(entries) < LOKI_LIMIT:
                start = stop
            elif entries[-1][0] == start:
                raise RuntimeError("a full Loki page shares one timestamp")
            else:
                start = entries[-1][0]


def index_forever(index: Index, loki: Loki, since: int, interval: float) -> None:
    try:
        rescanned = time.monotonic()
        while True:
            cursor = index.cursor()
            # Alloy can deliver records after newer ones: re-read the last hour on every
            # poll, and two days hourly or after an outage, when backlogs arrive.
            overlap = (
                RESCAN_NS
                if time.monotonic() - rescanned >= RESCAN_SECONDS
                else OVERLAP_NS
            )
            start = since if cursor is None else max(since, cursor - overlap)
            try:
                for entries in loki.read(start, time.time_ns()):
                    index.ingest(entries)
                if overlap == RESCAN_NS:
                    rescanned = time.monotonic()
            except HTTPError as error:
                if error.code < 500:
                    raise
                rescanned = 0
                print(
                    f"usage-index: Loki HTTP {error.code}; retrying",
                    file=sys.stderr,
                    flush=True,
                )
            except (OSError, http.client.HTTPException) as error:
                rescanned = 0
                print(
                    f"usage-index: Loki unavailable ({error!r}); retrying",
                    file=sys.stderr,
                    flush=True,
                )
            time.sleep(interval)
    except BaseException:
        traceback.print_exc()
        os._exit(1)


class Server(ThreadingHTTPServer):
    def __init__(
        self,
        address: tuple[str, int],
        database: Path,
        pages: dict[str, Path],
        zone: ZoneInfo,
    ) -> None:
        super().__init__(address, Handler)
        self.database = database
        self.pages = pages
        self.zone = zone


type Action = Callable[[Views], Json | None]


class Handler(BaseHTTPRequestHandler):
    def app(self) -> Server:
        return cast(Server, self.server)

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        query = {key: values[-1] for key, values in parse_qs(url.query).items()}
        page = self.app().pages.get(url.path)
        if page:
            self.send(200, "text/html; charset=utf-8", page.read_bytes())
            return
        self.api(url.path, query)

    def do_POST(self) -> None:
        actions = {
            "/api/notes": (4096, Views.add_note),
            "/api/titles": (TITLE_LIMIT, Views.add_titles),
        }
        path = urlsplit(self.path).path
        if path not in actions:
            self.send(404, "text/plain", b"not found")
            return
        limit, action = actions[path]
        length = int(self.headers.get("Content-Length", "0"))
        # Requiring JSON forces a CORS preflight, so other sites cannot post.
        if self.headers.get("Content-Type") != "application/json" or length > limit:
            self.send(400, "text/plain", f"send JSON under {limit} bytes".encode())
            return
        body = self.rfile.read(length)
        self.with_views(lambda views: action(views, cast(Json, json.loads(body))))

    def do_DELETE(self) -> None:
        path = urlsplit(self.path).path
        if not path.startswith("/api/notes/"):
            self.send(404, "text/plain", b"not found")
            return
        note = path.removeprefix("/api/notes/")
        self.with_views(lambda views: views.delete_note(int(note)))

    def api(self, path: str, query: dict[str, str]) -> None:
        models = (
            None
            if "models" not in query
            else [m for m in query["models"].split(",") if m]
        )
        if path == "/api/view":
            self.with_views(
                lambda views: views.view(
                    parse_window(query.get("a")), parse_window(query.get("b")), models
                )
            )
        elif path == "/api/conversation":
            self.with_views(
                lambda views: views.conversation(query["id"], query["through"], models)
            )
        else:
            self.send(404, "text/plain", b"not found")

    def with_views(self, action: Action) -> None:
        views = Views(self.app().database, self.app().zone)
        try:
            result = action(views)
        except (ValueError, KeyError) as error:
            self.send(400, "text/plain; charset=utf-8", str(error).encode())
            return
        finally:
            views.close()
        self.send(
            200, "application/json", json.dumps(result, separators=(",", ":")).encode()
        )

    def send(self, status: int, kind: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        if len(body) > 1024 and "gzip" in self.headers.get("Accept-Encoding", ""):
            body = gzip.compress(body, compresslevel=5)
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


def parse_page(value: str) -> tuple[str, Path]:
    route, separator, file = value.partition("=")
    if not separator or not route.startswith("/"):
        raise argparse.ArgumentTypeError(f"expected /ROUTE=FILE, got {value!r}")
    return route, Path(file)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loki", required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument(
        "--page",
        type=parse_page,
        action="append",
        required=True,
        metavar="ROUTE=FILE",
        help="serve FILE at ROUTE; repeat for each page",
    )
    parser.add_argument("--listen", required=True, help="HOST:PORT")
    parser.add_argument("--since", type=date.fromisoformat, required=True)
    parser.add_argument("--timezone", type=ZoneInfo, required=True)
    parser.add_argument("--inbox-zero-key-hash", action="append", default=[])
    parser.add_argument("--interval", type=float, default=15)
    args = parser.parse_args()
    zone = cast(ZoneInfo, args.timezone)
    index = Index(args.database, zone, frozenset(args.inbox_zero_key_hash))
    since = cast(date, args.since)
    start = (
        int(datetime(since.year, since.month, since.day, tzinfo=zone).timestamp())
        * 10**9
    )
    threading.Thread(
        target=index_forever,
        args=(index, Loki(args.loki), start, args.interval),
        daemon=True,
    ).start()
    host, port = cast(str, args.listen).rsplit(":", 1)
    pages = dict(cast(list[tuple[str, Path]], args.page))
    Server((host, int(port)), args.database, pages, zone).serve_forever()


if __name__ == "__main__":
    main()
