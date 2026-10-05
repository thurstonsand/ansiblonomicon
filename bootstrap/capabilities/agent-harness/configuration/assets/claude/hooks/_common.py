"""Shared utilities for auto-title hook scripts."""

from __future__ import annotations

from datetime import datetime
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import NamedTuple, TypedDict, cast
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


class TitleConfig(NamedTuple):
    api_url: str
    max_message_bytes: int
    model: str
    prompt: str
    token: str


def load_title_config() -> TitleConfig:
    """Load the generated config from HOME, not the symlinked script directory."""
    path = Path.home() / ".claude/hooks/_config.py"
    spec = importlib.util.spec_from_file_location("claude_title_hook_config", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load title hook configuration: {path}")
    module = ModuleType(spec.name)
    spec.loader.exec_module(module)
    return TitleConfig(
        api_url=module.API_URL,
        max_message_bytes=module.MAX_MESSAGE_BYTES,
        model=module.MODEL,
        prompt=module.TITLE_PROMPT,
        token=module.TOKEN,
    )


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
    context: str,
    prompt: str,
    api_url: str,
    model: str,
    token: str,
    max_message_bytes: int,
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

    # Doppelclaude admits markerless requests only within a serialized message
    # budget, so keep the newest transcript tail that fits.
    while True:
        messages = [{"role": "user", "content": f"{prompt}\n\n{context}"}]
        overflow = len(json.dumps(messages, ensure_ascii=False).encode()) - (
            max_message_bytes
        )
        if overflow <= 0:
            break
        context = context[overflow:]

    body = json.dumps(
        {"model": model, "max_tokens": 60, "stream": True, "messages": messages},
        ensure_ascii=False,
    ).encode()

    req = urllib.request.Request(api_url, data=body, headers=headers, method="POST")

    text: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            for raw in resp:
                line = raw.decode().strip()
                if not line.startswith("data:"):
                    continue
                event: dict[str, object] = json.loads(line.removeprefix("data:"))
                if event.get("type") == "error":
                    raise TitleRequestError(f"API stream error: {event.get('error')}")
                if event.get("type") == "content_block_delta":
                    delta = cast(dict[str, object], event["delta"])
                    if delta["type"] == "text_delta":
                        text.append(str(delta["text"]))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise TitleRequestError(f"API request failed: {exc}") from exc

    title = "".join(text).strip()
    if not title:
        raise TitleRequestError("API response contained no text content")
    return title


def generate_title(
    session_id: str,
    cwd: str,
    transcript: str,
    *,
    api_url: str,
    model: str,
    token: str,
    prompt: str,
    max_message_bytes: int,
    hint: str | None = None,
) -> str:
    """Full pipeline: read transcript, call API. Returns generated title.

    Raises TitleRequestError on API failure, ValueError if prerequisites missing.
    """
    context = _read_transcript_context(transcript)
    if not context:
        raise ValueError("transcript has no user content")

    effective_prompt = prompt
    if hint:
        effective_prompt = (
            f"{prompt}\n\n"
            f"The user provided this context for titling the session: {hint}"
        )
    return post_title_request(
        context, effective_prompt, api_url, model, token, max_message_bytes
    )


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
