"""Shared utilities for auto-title hook scripts."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import TypedDict, cast
import urllib.error
import urllib.request

_TITLE_DIR = Path("/tmp/claude-session-titles")
_LOG_PATH = Path("/tmp/claude-code-auto-title.log")


class HookInput(TypedDict):
    session_id: str
    cwd: str
    transcript_path: str
    agent_id: str | None


class TitleRequestError(Exception):
    pass


# ---------------------------------------------------------------------------
# Title file handoff
# ---------------------------------------------------------------------------


def consume_pending_title(session_id: str) -> str | None:
    path = _TITLE_DIR / f"{session_id}.txt"
    if not path.is_file():
        return None
    title = path.read_text()
    path.unlink()
    return title or None


def write_pending_title(session_id: str, title: str) -> None:
    _TITLE_DIR.mkdir(parents=True, exist_ok=True)
    (_TITLE_DIR / f"{session_id}.txt").write_text(title)


# ---------------------------------------------------------------------------
# Transcript helpers
# ---------------------------------------------------------------------------


def read_current_title(transcript: str) -> str | None:
    """Return the most recent custom title from the transcript, or None."""
    title = None
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
                title = entry.get("customTitle")
    return title


def _read_transcript_context(transcript: str) -> str | None:
    """Read transcript content starting from the first user message."""
    lines: list[str] = []
    found_user = False
    with open(transcript) as f:
        for raw in f:
            stripped = raw.strip()
            if not stripped:
                continue
            if not found_user:
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "user":
                    continue
                found_user = True
            lines.append(stripped)
    return "\n".join(lines) or None


# ---------------------------------------------------------------------------
# API + title generation
# ---------------------------------------------------------------------------


def post_title_request(
    context: str, prompt: str, base_url: str, model: str, token: str
) -> str:
    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
        "User-Agent": "claude-code-auto-title",
    }

    if model.endswith("[1m]"):
        model = model[: -len("[1m]")]
        headers["anthropic-beta"] = "context-1m-2025-08-07"

    body = json.dumps(
        {
            "model": model,
            "max_tokens": 60,
            "messages": [{"role": "user", "content": f"{prompt}\n\n{context}"}],
        }
    ).encode()

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/messages",
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result: dict[str, object] = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise TitleRequestError(f"API request failed: {exc}") from exc

    content = result.get("content")
    if not isinstance(content, list):
        raise TitleRequestError("API response contained no text content")

    blocks = cast(list[dict[str, object]], content)
    for block in blocks:
        if block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                return text.strip()

    raise TitleRequestError("API response contained no text content")


def generate_title(
    session_id: str,
    cwd: str,
    transcript: str,
    *,
    api_url: str,
    model: str,
    token: str,
    prompt: str,
    max_context_bytes: int,
    hint: str | None = None,
) -> str:
    """Full pipeline: read transcript, call API. Returns generated title.

    Raises TitleRequestError on API failure, ValueError if prerequisites missing.
    """
    context = _read_transcript_context(transcript)
    if not context:
        raise ValueError("transcript has no user content")

    context = context[-max_context_bytes:]

    effective_prompt = prompt
    if hint:
        effective_prompt = (
            f"{prompt}\n\n"
            f"The user provided this context for titling the session: {hint}"
        )
    return post_title_request(context, effective_prompt, api_url, model, token)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def log(session_id: str, cwd: str, msg: str) -> None:
    try:
        with open(_LOG_PATH, "a") as f:
            f.write(
                f"[{datetime.now().isoformat(timespec='seconds')}] "
                f"session={session_id} cwd={cwd} {msg}\n"
            )
    except OSError:
        pass
