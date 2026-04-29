#!/usr/bin/env python3
"""UserPromptSubmit hook: apply explicit <title> tags or pick up auto-generated titles."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import cast

from _common import HookInput, has_custom_title, read_title

_TITLE_TAG_RE = re.compile(r"<title>([^<]+)</title>")


class PromptHookInput(HookInput):
    prompt: str


def _emit_title(title: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "sessionTitle": title,
            }
        },
        sys.stdout,
    )


def main() -> None:
    hook = cast(PromptHookInput, json.load(sys.stdin))

    if hook.get("agent_id"):
        return

    match = _TITLE_TAG_RE.search(hook["prompt"])
    if match:
        _emit_title(match.group(1))
        return

    title = read_title(hook["session_id"])
    if not title:
        return

    transcript = hook["transcript_path"]
    if os.path.isfile(transcript) and has_custom_title(transcript):
        return

    _emit_title(title)


if __name__ == "__main__":
    main()
