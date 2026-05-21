#!/usr/bin/env python3
"""UserPromptSubmit hook: apply explicit {title} tags or pick up auto-generated titles."""

from __future__ import annotations

import json
import re
import sys
from typing import cast

from _common import HookInput, consume_pending_title, log

_TITLE_TAG_RE = re.compile(r"\{title\}(.+?)\{/title\}")


class PromptHookInput(HookInput):
    prompt: str


def _emit_title(title: str, session_id: str, cwd: str, source: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "sessionTitle": title,
            }
        },
        sys.stdout,
    )
    log(session_id, cwd, f'emitted title "{title}" (source={source})')


def main() -> None:
    hook = cast(PromptHookInput, json.load(sys.stdin))

    if hook.get("agent_id"):
        return

    session_id = hook["session_id"]
    cwd = hook["cwd"]

    pending = consume_pending_title(session_id)
    match = _TITLE_TAG_RE.search(hook["prompt"])

    title, source = (match.group(1), "tag") if match else (pending, "generated")
    if title:
        _emit_title(title, session_id, cwd, source)


if __name__ == "__main__":
    main()
