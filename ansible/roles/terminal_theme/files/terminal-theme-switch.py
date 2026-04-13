#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["tomlkit>=0.13.2"]
# ///
"""Applies side effects when the terminal switches between dark and light mode.

Called by tmux hooks (Mode 2031) and zsh helper functions.
"""

from collections.abc import MutableMapping
import json
from pathlib import Path
import sys
from typing import Literal, cast

from tomlkit import document, parse, table

Mode = Literal["dark", "light"]
VALID_MODES: set[Mode] = {"dark", "light"}
TomlMapping = MutableMapping[str, object]


def update_terminal_bg(mode: Mode) -> None:
    Path.home().joinpath(".terminal-bg").write_text(mode + "\n")


def update_claude_theme(mode: Mode) -> None:
    claude_json = Path.home() / ".claude.json"
    if not claude_json.exists():
        return
    config: dict[str, object] = json.loads(claude_json.read_text())
    config["theme"] = mode
    claude_json.write_text(json.dumps(config, indent=2) + "\n")


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


def hunk_theme_name(mode: Mode) -> str:
    return "paper" if mode == "light" else "graphite"


def set_hunk_theme(text: str, mode: Mode) -> str:
    root = parse(text) if text.strip() else document()
    root["theme"] = hunk_theme_name(mode)
    return root.as_string()


def update_hunk_theme(mode: Mode) -> None:
    hunk_toml = Path.home() / ".config" / "hunk" / "config.toml"
    hunk_toml.parent.mkdir(parents=True, exist_ok=True)
    existing = hunk_toml.read_text() if hunk_toml.exists() else ""
    updated = set_hunk_theme(existing, mode)
    hunk_toml.write_text(updated)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in VALID_MODES:
        print(f"Usage: python3 {sys.argv[0]} <dark|light>", file=sys.stderr)
        sys.exit(1)

    mode: Mode = sys.argv[1]  # type: ignore[assignment]
    update_terminal_bg(mode)
    update_claude_theme(mode)
    update_codex_theme(mode)
    update_hunk_theme(mode)


if __name__ == "__main__":
    main()
