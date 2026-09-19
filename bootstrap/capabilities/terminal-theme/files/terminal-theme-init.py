#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# ///
"""Seed terminal theme state before native dotfile templates render."""

import argparse
from pathlib import Path
import subprocess

from terminal_theme_common import Mode, write_atomic


def initial_mode(profile: str) -> Mode:
    state = Path.home() / ".terminal-bg"
    if state.exists():
        return Mode(state.read_text(encoding="utf-8").strip())
    if (
        profile == "detector"
        and subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    ):
        return Mode.DARK
    return Mode.LIGHT if profile == "detector" else Mode.DARK


def reconcile(profile: str) -> None:
    mode = initial_mode(profile)
    state = Path.home() / ".terminal-bg"
    if not state.exists():
        write_atomic(state, f"{mode}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=("detector", "mirror"))
    args = parser.parse_args()
    reconcile(args.profile)


if __name__ == "__main__":
    main()
