#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["tomlkit>=0.13.2"]
# ///
"""Hand the active Omarchy theme to Codex: its TUI syntax theme and its desktop chrome."""

from pathlib import Path

import tomlkit

home = Path.home()
theme = home / ".local/state/omarchy/current/theme"

tm_theme = home / ".codex/themes/omarchy.tmTheme"
tm_theme.parent.mkdir(parents=True, exist_ok=True)
staged_theme = tm_theme.with_name(f"{tm_theme.name}.omarchy")
staged_theme.write_text((theme / "syntax.tmTheme").read_text())
staged_theme.replace(tm_theme)

# A fresh home reaches this before agent-config, which merges into whatever it finds here.
config_path = home / ".codex/config.toml"
config_path.touch(mode=0o600)
chrome = tomlkit.parse((theme / "codex-chrome.toml").read_text())
config = tomlkit.parse(config_path.read_text())
desktop = config.setdefault("desktop", tomlkit.table())
for name, table in chrome["desktop"].items():
    desktop[name] = table

# agent-config keeps this file private; the staged copy must not widen it.
staged = config_path.with_name(f"{config_path.name}.omarchy")
staged.touch(mode=config_path.stat().st_mode & 0o777, exist_ok=False)
staged.write_text(tomlkit.dumps(config))
staged.replace(config_path)
