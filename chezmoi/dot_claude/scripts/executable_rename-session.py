#!/usr/bin/env python3
"""Rename the current Claude Code session.

Updates both the live PID file and the JSONL conversation log so the name
persists across session resumes.
"""

import glob
import json
import os
import sys


def find_jsonl(session_id: str, projects_dir: str) -> str | None:
    """Find the JSONL file for a session ID."""
    pattern = os.path.join(projects_dir, "**", f"{session_id}.jsonl")
    matches = glob.glob(pattern, recursive=True)
    return matches[0] if matches else None


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: rename-session.py [-r] <claude_pid> <name>",
            file=sys.stderr,
        )
        print("  -r          retitle an already-named session", file=sys.stderr)
        print("  claude_pid  pass $PPID from the calling shell", file=sys.stderr)
        sys.exit(1)

    args = sys.argv[1:]
    retitle = False
    if args[0] == "-r":
        retitle = True
        args = args[1:]

    if len(args) < 2:
        print("Error: missing <claude_pid> or <name>", file=sys.stderr)
        sys.exit(1)

    pid = args[0]
    name = args[1]
    session_file = os.path.expanduser(f"~/.claude/sessions/{pid}.json")

    if not os.path.isfile(session_file):
        print(f"Session file not found: {session_file}", file=sys.stderr)
        sys.exit(1)

    with open(session_file) as f:
        data = json.load(f)

    existing_name = data.get("name", "")
    if existing_name and not retitle:
        print(
            f"Error: session already titled '{existing_name}'. "
            "This probably means a title was already set earlier in this "
            "session. If you are a subagent, do not rename — this is not "
            "your responsibility. Only pass -r if you are intentionally "
            "retitling.",
            file=sys.stderr,
        )
        sys.exit(1)

    session_id = data.get("sessionId", "")
    data["name"] = name

    with open(session_file, "w") as f:
        json.dump(data, f)

    if session_id:
        projects_dir = os.path.expanduser("~/.claude/projects")
        jsonl_path = find_jsonl(session_id, projects_dir)
        if jsonl_path:
            with open(jsonl_path, "a") as f:
                for entry in [
                    {
                        "type": "custom-title",
                        "customTitle": name,
                        "sessionId": session_id,
                    },
                    {"type": "agent-name", "agentName": name, "sessionId": session_id},
                ]:
                    f.write(json.dumps(entry) + "\n")

    print(f"Session renamed to: {name}")


if __name__ == "__main__":
    main()
