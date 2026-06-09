#!/usr/bin/env python3
"""Produce a terminal tab title: {prefix}:{repo}[:{branch}] with worktree awareness."""

import argparse
import json
import os
import subprocess
import sys

MAINLINE_BRANCHES = {"main", "master"}


def git(cwd: str, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError, subprocess.CalledProcessError:
        return None
    return result.stdout.strip() or None


def is_linked_worktree(cwd: str) -> bool:
    git_dir = git(cwd, "rev-parse", "--git-dir")
    common_dir = git(cwd, "rev-parse", "--git-common-dir")
    if not git_dir or not common_dir:
        return False

    def resolve(p: str) -> str:
        full = p if os.path.isabs(p) else os.path.join(cwd, p)
        return os.path.realpath(full)

    return resolve(git_dir) != resolve(common_dir)


def compute_title(prefix: str, cwd: str) -> str:
    basename = os.path.basename(cwd) or cwd

    if git(cwd, "rev-parse", "--is-inside-work-tree") != "true":
        return f"{prefix}:{basename}"

    branch = git(cwd, "branch", "--show-current")

    if is_linked_worktree(cwd):
        return (
            f"{prefix}:wt:{basename}:{branch}" if branch else f"{prefix}:wt:{basename}"
        )

    if branch and branch not in MAINLINE_BRANCHES and not branch.endswith("/HEAD"):
        return f"{prefix}:{basename}:{branch}"

    return f"{prefix}:{basename}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--claude-hook",
        action="store_true",
        help="read SessionStart JSON on stdin, emit hook JSON",
    )
    mode.add_argument("--nvim", action="store_true", help="print nvim title to stdout")
    parser.add_argument(
        "cwd", nargs="?", default=os.getcwd(), help="working directory (default: $PWD)"
    )

    args = parser.parse_args()

    if args.claude_hook:
        hook = json.load(sys.stdin)
        title = compute_title("claude", hook["cwd"])
        json.dump({"terminalSequence": f"\033]2;{title}\007"}, sys.stdout)
    else:
        print(compute_title("nvim", args.cwd))


if __name__ == "__main__":
    main()
