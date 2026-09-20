#!/usr/bin/env python3
"""Safely fast-forward the overlay-bearing uvc-util checkout."""

import argparse
from pathlib import Path
import subprocess
import sys


def git(repo: Path, *args: str, capture: bool = False) -> str:
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def validate(repo: Path, origin: str) -> None:
    if git(repo, "remote", "get-url", "origin", capture=True) != origin:
        raise RuntimeError("uvc-util origin does not match the declared repository")
    if git(repo, "status", "--porcelain", "--untracked-files=no", capture=True):
        raise RuntimeError("uvc-util has tracked changes; refusing to update")


def remote_main(origin: str) -> str:
    result = subprocess.run(
        ["git", "ls-remote", origin, "refs/heads/main"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.split()
    if len(result) != 2 or result[1] != "refs/heads/main":
        raise RuntimeError("uvc-util origin has no main branch")
    return result[0]


def compare(repo: Path, local: str, remote: str, *, check: bool) -> bool:
    if local == remote:
        return False
    known = (
        subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"{remote}^{{commit}}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )
    if not known:
        if check:
            print(
                "uvc-util origin/main differs; ancestry is unavailable without fetching",
                file=sys.stderr,
            )
            return True
        raise RuntimeError("uvc-util fetched main commit is unavailable locally")
    base = git(repo, "merge-base", local, remote, capture=True)
    if base != local:
        raise RuntimeError("uvc-util main has diverged; refusing to reset or merge")
    if check:
        print("uvc-util origin/main has advanced", file=sys.stderr)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    repo: Path = args.repo
    if not repo.exists():
        if args.check:
            print(f"uvc-util checkout would be cloned: {repo}", file=sys.stderr)
            return 0
        repo.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--branch", "main", args.origin, str(repo)], check=True
        )
        return 0
    validate(repo, args.origin)
    if args.check:
        remote = remote_main(args.origin)
        local = git(repo, "rev-parse", "main", capture=True)
        compare(repo, local, remote, check=True)
        if git(repo, "branch", "--show-current", capture=True) != "main":
            print("uvc-util checkout would switch to main", file=sys.stderr)
        return 0
    git(repo, "fetch", "--prune", "origin", "main")
    local = git(repo, "rev-parse", "main", capture=True)
    remote = git(repo, "rev-parse", "FETCH_HEAD", capture=True)
    advanced = compare(repo, local, remote, check=False)
    git(repo, "checkout", "main")
    if advanced:
        git(repo, "merge", "--ff-only", remote)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"uvc-repo: {error}", file=sys.stderr)
        raise SystemExit(1) from error
