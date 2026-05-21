#!/usr/bin/env python3
"""SessionStart hook: set terminal tab title via OSC 2."""

import json
import os
import sys
from typing import Literal, TypedDict, cast


class SessionStartInput(TypedDict):
    session_id: str
    cwd: str
    transcript_path: str
    hook_event_name: Literal["SessionStart"]
    source: Literal["startup", "resume", "clear", "compact"]
    model: str
    agent_id: str | None
    agent_type: str | None


def main() -> None:
    hook = cast(SessionStartInput, json.load(sys.stdin))
    cwd = hook["cwd"]
    wt_root = os.path.expanduser("~/.wt/worktrees/")
    if cwd.startswith(wt_root):
        name = os.path.basename(cwd)
        title = f"claude:wt:{name}"
    else:
        title = f"claude:{os.path.basename(cwd)}"

    seq = f"\033]2;{title}\007"
    json.dump({"terminalSequence": seq}, sys.stdout)


if __name__ == "__main__":
    main()
