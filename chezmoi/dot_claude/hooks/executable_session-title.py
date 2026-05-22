#!/usr/bin/env python3
"""SessionStart hook: set terminal tab title via OSC 2."""

import json
import os
import subprocess
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


MAINLINE_BRANCHES = {"main", "master"}


def git(cwd: str, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    return result.stdout.strip() or None


def normalize_git_path(cwd: str, git_path: str) -> str:
    path = git_path if os.path.isabs(git_path) else os.path.join(cwd, git_path)
    return os.path.realpath(path)


def is_in_git_repo(cwd: str) -> bool:
    return git(cwd, ["rev-parse", "--is-inside-work-tree"]) == "true"


def is_linked_worktree(cwd: str) -> bool:
    git_dir = git(cwd, ["rev-parse", "--git-dir"])
    common_dir = git(cwd, ["rev-parse", "--git-common-dir"])

    if not git_dir or not common_dir:
        return False

    return normalize_git_path(cwd, git_dir) != normalize_git_path(cwd, common_dir)


def current_branch(cwd: str) -> str | None:
    return git(cwd, ["branch", "--show-current"])


def should_show_main_worktree_branch(branch: str | None) -> bool:
    if not branch:
        return False
    if branch in MAINLINE_BRANCHES:
        return False
    return branch != "HEAD" and not branch.endswith("/HEAD")


def title_for(cwd: str) -> str:
    cwd_name = os.path.basename(cwd) or cwd

    if not is_in_git_repo(cwd):
        return f"claude:{cwd_name}"

    branch = current_branch(cwd)

    if is_linked_worktree(cwd):
        return f"claude:wt:{cwd_name}:{branch}" if branch else f"claude:wt:{cwd_name}"

    return (
        f"claude:{cwd_name}:{branch}"
        if should_show_main_worktree_branch(branch)
        else f"claude:{cwd_name}"
    )


def main() -> None:
    hook = cast(SessionStartInput, json.load(sys.stdin))
    title = title_for(hook["cwd"])

    seq = f"\033]2;{title}\007"
    json.dump({"terminalSequence": seq}, sys.stdout)


if __name__ == "__main__":
    main()
