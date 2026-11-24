"""Add advisory shell timing to Claude, Codex, and Antigravity without changing tool results."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any


def _format_timing(label: str, seconds: float) -> str:
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
        return _format_timing(label, seconds)


def agy_response(
    event: dict[str, Any], database: Path, *, now: float | None = None
) -> dict[str, Any]:
    """Handle Antigravity PreToolUse, PostToolUse, and PreInvocation hooks.

    Antigravity's PostToolUse cannot return additionalContext, so slow commands
    (>60s, matching Pi so persistent injected steps do not bloat context) are
    queued in SQLite and emitted on the next PreInvocation.
    """
    hook = event.get("hookEventName")
    scope = str(event["conversationId"])
    timestamp = time.time() if now is None else now
    database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with closing(sqlite3.connect(database)) as db, db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS calls "
            "(scope TEXT, id TEXT, started REAL, PRIMARY KEY(scope, id))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS pending "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, created REAL, message TEXT)"
        )
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM calls WHERE started < ?", (timestamp - 86400,))
        db.execute("DELETE FROM pending WHERE created < ?", (timestamp - 86400,))
        if hook == "PreToolUse":
            tool_call = event.get("toolCall", {})
            if tool_call.get("name") == "run_command":
                call = str(tool_call.get("id") or event.get("stepIdx"))
                db.execute(
                    "INSERT OR REPLACE INTO calls VALUES (?, ?, ?)",
                    (scope, call, timestamp),
                )
            return {"decision": "allow"}
        if hook == "PostToolUse":
            tool_call = event.get("toolCall", {})
            if tool_call.get("name") == "run_command":
                call = str(tool_call.get("id") or event.get("stepIdx"))
                started = db.execute(
                    "DELETE FROM calls WHERE scope = ? AND id = ? RETURNING started",
                    (scope, call),
                ).fetchone()
                if started is not None:
                    seconds = timestamp - started[0]
                    if seconds > 60:
                        message = _format_timing(
                            "Shell tool elapsed (includes hook/approval wait)", seconds
                        )
                        db.execute(
                            "INSERT INTO pending (scope, created, message) VALUES (?, ?, ?)",
                            (scope, timestamp, message),
                        )
            return {}
        if hook == "PreInvocation":
            rows = db.execute(
                "DELETE FROM pending WHERE scope = ? RETURNING message",
                (scope,),
            ).fetchall()
            if rows:
                combined = "\n".join(row[0] for row in rows)
                return {
                    "injectSteps": [
                        {"systemMessage": {"systemMessage": combined}},
                    ]
                }
            return {}
        return {}


def main() -> None:
    harness = sys.argv[1]
    if harness not in {"claude", "codex", "agy"}:
        raise ValueError(f"Unsupported harness: {harness}")
    event = json.load(sys.stdin)
    database = Path.home() / f".cache/command-timing/{harness}.sqlite3"
    if harness == "agy":
        print(json.dumps(agy_response(event, database)))
        return
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
