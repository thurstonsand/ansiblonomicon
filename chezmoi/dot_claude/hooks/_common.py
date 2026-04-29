"""Shared utilities for auto-title hook scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

_TITLE_DIR = Path("/tmp/claude-session-titles")


class HookInput(TypedDict):
    session_id: str
    transcript_path: str
    agent_id: str | None


def read_title(session_id: str) -> str | None:
    path = _TITLE_DIR / f"{session_id}.txt"
    if not path.is_file():
        return None
    title = path.read_text()
    path.unlink()
    return title or None


def write_title(session_id: str, title: str) -> None:
    _TITLE_DIR.mkdir(parents=True, exist_ok=True)
    (_TITLE_DIR / f"{session_id}.txt").write_text(title)


def has_custom_title(transcript: str) -> bool:
    with open(transcript) as f:
        for raw_line in f:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if entry.get("type") == "custom-title":
                return True
    return False
