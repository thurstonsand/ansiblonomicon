#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["tomlkit>=0.13.2"]
# ///
"""Gruvbox Hard custom theme fragments for Hunk."""

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import tomllib

from terminal_theme_common import Mode
from tomlkit import document, dumps, table


@dataclass(frozen=True)
class CliArgs:
    mode: Mode


_SOURCE_DIR = Path(__file__).resolve().parent


def _load_theme(mode: Mode) -> Mapping[str, Mapping[str, str]]:
    palette = _SOURCE_DIR / f"hunk-gruvbox-{mode.value}.toml"
    parsed = tomllib.loads(palette.read_text())
    custom_theme = parsed["custom_theme"]
    syntax = custom_theme.pop("syntax")
    return {"custom_theme": custom_theme, "syntax": syntax}


HUNK_GRUVBOX_THEMES: Mapping[Mode, Mapping[str, Mapping[str, str]]] = {
    mode: _load_theme(mode) for mode in Mode
}


def hunk_custom_theme(mode: Mode) -> Mapping[str, Mapping[str, str]]:
    return HUNK_GRUVBOX_THEMES[mode]


def hunk_custom_theme_toml(mode: Mode) -> str:
    doc = document()
    doc["custom_theme"] = hunk_custom_theme_table(mode)
    return dumps(doc)


def hunk_custom_theme_table(mode: Mode):
    theme = hunk_custom_theme(mode)
    custom_theme = table()
    syntax = table()

    for key, value in theme["custom_theme"].items():
        custom_theme[key] = value
    for key, value in theme["syntax"].items():
        syntax[key] = value

    custom_theme["syntax"] = syntax
    return custom_theme


def parse_args() -> CliArgs:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", type=Mode)
    args = parser.parse_args()
    return CliArgs(mode=args.mode)


def main() -> None:
    args = parse_args()
    print(hunk_custom_theme_toml(args.mode), end="")


if __name__ == "__main__":
    main()
