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


def _added_lines_from_file(path: Path, content: str) -> list[str]:
    previous: list[str] = path.read_text().splitlines() if path.exists() else []
    return [line for line in content.splitlines() if line not in previous]


def violates(event: dict[str, Any]) -> bool:
    if "toolCall" in event:
        tool = event["toolCall"].get("name")
        args = event["toolCall"].get("args", {})
        cwd = Path(event.get("cwd", "."))
        if tool == "edit_file":
            old = str(args.get("Target", "")).splitlines()
            lines = [
                line
                for line in str(args.get("Replacement", "")).splitlines()
                if line not in old
            ]
        elif tool == "replace_file_content":
            old = str(args.get("TargetContent", "")).splitlines()
            lines = [
                line
                for line in str(args.get("ReplacementContent", "")).splitlines()
                if line not in old
            ]
        elif tool == "multi_replace_file_content":
            lines = [
                line
                for chunk in args.get("ReplacementChunks", [])
                for line in str(chunk.get("ReplacementContent", "")).splitlines()
                if line not in str(chunk.get("TargetContent", "")).splitlines()
            ]
        elif tool == "write_file":
            path = cwd / str(args["Path"])
            lines = _added_lines_from_file(path, str(args.get("Content", "")))
        elif tool == "write_to_file":
            path = cwd / str(args["TargetFile"])
            lines = _added_lines_from_file(path, str(args.get("CodeContent", "")))
        else:
            return False
        return any(PATTERN.search(line) for line in lines)

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
        lines = _added_lines_from_file(path, args["content"])
    else:
        return False
    return any(PATTERN.search(line) for line in lines)


if __name__ == "__main__":
    harness = sys.argv[1] if len(sys.argv) > 1 else ""
    payload = json.load(sys.stdin)
    blocked = violates(payload)
    if harness == "agy":
        if blocked:
            print(json.dumps({"decision": "deny", "reason": REASON}))
        else:
            print(json.dumps({"decision": "allow"}))
    elif blocked:
        print(REASON, file=sys.stderr)
        sys.exit(2)
