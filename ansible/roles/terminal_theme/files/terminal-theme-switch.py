#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["tomlkit>=0.13.2"]
# ///
"""Applies side effects when the terminal switches between dark and light mode.

Called by dark-notify, tmux hooks (Mode 2031), zsh helper functions, and SSH
mirror syncs.
"""

import argparse
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from hunk_gruvbox_theme import hunk_custom_theme_table
from terminal_theme_common import (
    Mode,
    ThemeLease,
    sync_mirror,
    write_atomic,
)
from tomlkit import parse, table

TomlMapping = MutableMapping[str, object]


@dataclass(frozen=True)
class CliArgs:
    mode: Mode
    no_mirror_sync: bool


def update_terminal_bg(mode: Mode) -> None:
    Path.home().joinpath(".terminal-bg").write_text(mode + "\n")


def codex_theme_name(mode: Mode) -> str:
    return f"gruvbox-{mode}"


def set_codex_tui_theme(text: str, mode: Mode) -> str:
    raw_document = parse(text)
    document = cast(TomlMapping, raw_document)
    tui = cast(TomlMapping | None, document.get("tui"))
    if tui is None:
        tui = cast(TomlMapping, table())
        document["tui"] = tui
    tui["theme"] = codex_theme_name(mode)
    return raw_document.as_string()


def update_codex_theme(mode: Mode) -> None:
    codex_toml = Path.home() / ".codex" / "config.toml"
    if not codex_toml.exists():
        return

    updated = set_codex_tui_theme(codex_toml.read_text(), mode)
    codex_toml.write_text(updated)


def set_hunk_theme(text: str, mode: Mode) -> str:
    root = parse(text)
    root["custom_theme"] = hunk_custom_theme_table(mode)
    return root.as_string()


def update_hunk_theme(mode: Mode) -> None:
    hunk_toml = Path.home() / ".config" / "hunk" / "config.toml"
    if not hunk_toml.exists():
        return

    updated = set_hunk_theme(hunk_toml.read_text(), mode)
    write_atomic(hunk_toml, updated)


def sync_active_mirrors(mode: Mode) -> None:
    for host in sorted(ThemeLease.active_hosts()):
        sync_mirror(host, mode)


def parse_args() -> CliArgs:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-mirror-sync", action="store_true")
    parser.add_argument("mode", type=Mode)
    args = parser.parse_args()
    return CliArgs(
        mode=args.mode,
        no_mirror_sync=bool(args.no_mirror_sync),
    )


def main() -> None:
    args = parse_args()
    update_terminal_bg(args.mode)
    update_codex_theme(args.mode)
    update_hunk_theme(args.mode)
    if not args.no_mirror_sync:
        sync_active_mirrors(args.mode)


if __name__ == "__main__":
    main()
