#!/usr/bin/env python3
"""UserPromptSubmit hook: apply explicit <title> tags or pick up auto-generated titles."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import cast

from _common import HookInput, has_custom_title, log, read_title

_TITLE_TAG_RE = re.compile(r"<title>([^<]+)</title>")


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

    match = _TITLE_TAG_RE.search(hook["prompt"])
    if match:
        _emit_title(match.group(1), session_id, cwd, "tag")
        return

    title = read_title(session_id)
    if not title:
        return

    transcript = hook["transcript_path"]
    if os.path.isfile(transcript) and has_custom_title(transcript):
        return

    _emit_title(title, session_id, cwd, "generated")


if __name__ == "__main__":
    main()
