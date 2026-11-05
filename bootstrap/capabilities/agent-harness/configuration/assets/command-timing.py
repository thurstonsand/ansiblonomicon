"""Add advisory shell timing to Claude and Codex without changing tool results."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any


def feedback(event: dict[str, Any], database: Path) -> str | None:
    if event["tool_name"] != "Bash":
        return None
    now = time.time()
    scope = json.dumps([event["session_id"], event.get("agent_id")])
    call = event["tool_use_id"]
    database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sqlite3.connect(database) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS calls "
            "(scope TEXT, id TEXT, started REAL, PRIMARY KEY(scope, id))"
        )
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM calls WHERE started < ?", (now - 86400,))
        if event["hook_event_name"] == "PreToolUse":
            db.execute(
                "INSERT OR REPLACE INTO calls VALUES (?, ?, ?)", (scope, call, now)
            )
            return None
        started = db.execute(
            "DELETE FROM calls WHERE scope = ? AND id = ? RETURNING started",
            (scope, call),
        ).fetchone()
        duration = event.get("duration_ms")
        if duration is not None:
            seconds = duration / 1000
            label = "Shell tool execution"
        elif started is not None:
            seconds = now - started[0]
            label = "Shell tool elapsed (includes hook/approval wait)"
        else:
            return None
        message = f"[command-timing] {label}: {seconds:.1f}s."
        if seconds > 300:
            message += " Very slow feedback loop: over 5 minutes. Change the iteration strategy before repeating this command."
        elif seconds > 60:
            message += " Slow feedback loop: over 60 seconds."
        if seconds > 60:
            message += (
                " Find a narrower test, file, or reproduction for the next edit."
                " Keep required full-suite validation for the final check; don't skip verification."
            )
        return (
            message
            + " Background launches measure the tool call, not the detached command's lifetime."
        )


def main() -> None:
    harness = sys.argv[1]
    if harness not in {"claude", "codex"}:
        raise ValueError(f"Unsupported harness: {harness}")
    event = json.load(sys.stdin)
    database = Path.home() / f".cache/command-timing/{harness}.sqlite3"
    message = feedback(event, database)
    if message is not None:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": event["hook_event_name"],
                        "additionalContext": message,
                    }
                }
            )
        )


if __name__ == "__main__":
    main()
