"""Reject newly added full-line comments that narrate the editing conversation."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any

PATTERN = re.compile(
    r"^\s*(?://|#|/\*|\*|<!--).*\b"
    r"(?:changed from|used to be|previously (?:this|it)|as (?:you )?requested)\b",
    re.IGNORECASE,
)
REASON = (
    "Write comments for the code, not the chat. Explain current behavior and rationale; "
    "remove conversation or edit-history narration from the new comment."
)


def violates(event: dict[str, Any]) -> bool:
    tool = event["tool_name"]
    args = event["tool_input"]
    if tool == "apply_patch":
        lines = [
            line[1:] for line in args["command"].splitlines() if line.startswith("+")
        ]
    elif tool in {"Edit", "MultiEdit"}:
        edits = args["edits"] if tool == "MultiEdit" else [args]
        lines = [
            line
            for edit in edits
            for line in edit["new_string"].splitlines()
            if line not in edit["old_string"].splitlines()
        ]
    elif tool == "Write":
        path = Path(event["cwd"]) / args["file_path"]
        previous: list[str] = path.read_text().splitlines() if path.exists() else []
        lines = [line for line in args["content"].splitlines() if line not in previous]
    else:
        return False
    return any(PATTERN.search(line) for line in lines)


if __name__ == "__main__":
    if violates(json.load(sys.stdin)):
        print(REASON, file=sys.stderr)
        sys.exit(2)
