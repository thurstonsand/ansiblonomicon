#!/usr/bin/env python3
"""Drain CLIProxyAPI's destructive usage queue into a private, sanitized JSONL spool."""

import argparse
from datetime import UTC, datetime
import hashlib
import http.client
import json
import os
from pathlib import Path
import sys
import time
from typing import cast
from urllib.parse import urlsplit
from uuid import uuid4

type Json = bool | int | float | str | list[Json] | dict[str, Json] | None


def object_value(value: Json) -> dict[str, Json]:
    if not isinstance(value, dict):
        raise ValueError("expected object")
    return value


def text_value(value: Json) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("expected nonempty string")
    return value


def count_value(value: Json) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("expected nonnegative integer")
    return value


def normalize(value: Json) -> dict[str, Json]:
    record = object_value(value)
    timestamp = text_value(record.get("timestamp"))
    if datetime.fromisoformat(timestamp).tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    execution_id = text_value(record.get("execution_id"))
    failed = record.get("failed")
    if not isinstance(failed, bool):
        raise ValueError("failed must be boolean")
    event: dict[str, Json] = {
        "event": "usage",
        "schema_version": 1,
        "event_id": f"cpa:{execution_id}",
        "timestamp": timestamp,
        "collected_at": datetime.now(UTC).isoformat(),
        "usage_scope": "upstream_execution",
        "outcome": "error" if failed else "success",
    }
    for field in (
        "request_id",
        "execution_id",
        "trace_id",
        "session_id",
        "parent_session_id",
        "provider",
        "model",
        "response_model",
        "alias",
        "auth_type",
        "auth_index",
        "reasoning_effort",
        "service_tier",
        "effective_service_tier",
        "node_kind",
    ):
        entry = record.get(field)
        if entry is not None:
            if not isinstance(entry, str):
                raise ValueError("invalid metadata type")
            event[field] = entry
    key = record.get("api_key")
    if key:
        event["client_key_hash"] = hashlib.sha256(text_value(key).encode()).hexdigest()
    for field in ("latency_ms", "ttft_ms"):
        if record.get(field) is not None:
            event[field] = count_value(record[field])
    for field in ("is_fork", "is_compaction", "generate", "stream"):
        if record.get(field) is not None:
            if not isinstance(record[field], bool):
                raise ValueError("invalid boolean metadata")
            event[field] = record[field]
    failure = record.get("fail")
    if failure is not None:
        status = object_value(failure).get("status_code")
        if status is not None:
            event["http_status"] = count_value(status)

    # Older/unknown accounting stays visible but never becomes invented zero usage.
    breakdown = record.get("token_breakdown")
    event["accounting_quality"] = "unavailable"
    event["usage"] = None
    if breakdown is not None:
        accounting = object_value(breakdown)
        event["accounting_version"] = count_value(accounting.get("schema_version"))
        if accounting["schema_version"] == 2:
            quality = accounting.get("quality")
            if quality not in ("complete", "inconsistent", "unclassified"):
                raise ValueError("unknown accounting quality")
            inputs = object_value(accounting.get("input"))
            outputs = object_value(accounting.get("output"))
            uncached = count_value(inputs.get("uncached_tokens"))
            read = count_value(inputs.get("cache_read_tokens"))
            write = count_value(inputs.get("cache_write_tokens"))
            output = count_value(outputs.get("total_tokens"))
            reasoning = count_value(outputs.get("reasoning_tokens"))
            other_output = count_value(outputs.get("non_reasoning_tokens"))
            unclassified = count_value(accounting.get("unclassified_tokens"))
            total = count_value(accounting.get("total_tokens"))
            if (
                uncached + read + write != count_value(inputs.get("total_tokens"))
                or reasoning + other_output != output
                or uncached + read + write + output + unclassified != total
                or (quality == "complete" and unclassified != 0)
            ):
                raise ValueError("inconsistent token breakdown")
            event["accounting_quality"] = quality
            event["unclassified_tokens"] = unclassified
            event["token_breakdown"] = {
                "schema_version": 2,
                "quality": quality,
                "total_tokens": total,
                "input": {
                    "total_tokens": uncached + read + write,
                    "uncached_tokens": uncached,
                    "cache_read_tokens": read,
                    "cache_write_tokens": write,
                },
                "output": {
                    "total_tokens": output,
                    "non_reasoning_tokens": other_output,
                    "reasoning_tokens": reasoning,
                },
                "unclassified_tokens": unclassified,
            }
            if quality == "complete":
                event["usage"] = {
                    "input": uncached,
                    "cache_read": read,
                    "cache_creation": write,
                    "output": output,
                }
                # Reasoning is a subset of output, not another additive bucket.
                event["reasoning_tokens"] = reasoning
    return event


class Spool:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, events: list[dict[str, Json]]) -> None:
        if not events:
            return
        data = "".join(
            json.dumps(event, separators=(",", ":")) + "\n" for event in events
        )
        if self.path.exists() and self.path.stat().st_size >= 64 * 1024 * 1024:
            for index in range(7, 0, -1):
                old = Path(f"{self.path}.{index}")
                if old.exists():
                    old.replace(f"{self.path}.{index + 1}")
            self.path.replace(f"{self.path}.1")
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def notice(event: str, **fields: Json) -> dict[str, Json]:
    return {
        "event": event,
        "schema_version": 1,
        "event_id": str(uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        **fields,
    }


class QueueError(Exception):
    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"queue HTTP {status}")


def fetch(url: str, key: str) -> list[Json]:
    target = urlsplit(url)
    if target.scheme not in ("http", "https") or not target.hostname or target.username:
        raise ValueError("queue URL must be HTTP(S) without credentials")
    connection_type = (
        http.client.HTTPSConnection
        if target.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = connection_type(target.hostname, target.port, timeout=15)
    try:
        path = target.path + (f"?{target.query}" if target.query else "")
        connection.request("GET", path, headers={"Authorization": f"Bearer {key}"})
        response = connection.getresponse()
        if response.status != 200:
            # Never log response bodies or follow a redirect with the management key.
            raise QueueError(response.status)
        payload = cast(Json, json.loads(response.read()))
        if not isinstance(payload, list):
            raise ValueError("queue must return an array")
        return payload
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    key = args.key_file.read_text().strip()
    if not key:
        raise ValueError("empty management key")
    spool = Spool(args.output)
    spool.append([notice("collector_start", coverage="best_effort_destructive_queue")])
    failures = 0
    last_heartbeat = 0.0
    while True:
        try:
            batch = fetch(args.url, key)
        except (QueueError, OSError, http.client.HTTPException, ValueError) as error:
            failures += 1
            event = notice(
                "collector_error",
                category=type(error).__name__,
                http_status=error.status if isinstance(error, QueueError) else None,
                consecutive_failures=failures,
                coverage="possible_gap",
            )
            spool.append([event])
            print(json.dumps(event), file=sys.stderr, flush=True)
            if args.once or (
                isinstance(error, QueueError) and error.status in (401, 403)
            ):
                return 1
            time.sleep(min(5 * 2 ** min(failures - 1, 4), 60))
            continue
        events: list[dict[str, Json]] = []
        rejected = 0
        for value in batch:
            try:
                events.append(normalize(value))
            except (ValueError, TypeError):
                rejected += 1
        if rejected:
            events.append(
                notice("collector_rejected", records=rejected, coverage="gap")
            )
        if failures or time.monotonic() - last_heartbeat >= 300:
            events.append(
                notice("collector_poll", records=len(batch), recovered=failures > 0)
            )
            last_heartbeat = time.monotonic()
        # A write failure is fatal: never keep draining a destructive queue without storage.
        spool.append(events)
        failures = 0
        if args.once or rejected:
            return 1 if rejected else 0
        time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
