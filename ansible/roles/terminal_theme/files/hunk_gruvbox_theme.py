#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["tomlkit>=0.13.2"]
# ///
"""Gruvbox Hard custom theme fragments for Hunk."""

import argparse
from collections.abc import Mapping
from dataclasses import dataclass

from terminal_theme_common import Mode
from tomlkit import document, dumps, table


@dataclass(frozen=True)
class CliArgs:
    mode: Mode


HUNK_GRUVBOX_THEMES: Mapping[Mode, Mapping[str, Mapping[str, str]]] = {
    Mode.LIGHT: {
        "custom_theme": {
            "label": "Gruvbox Light Hard",
            "background": "#f9f5d7",
            "panel": "#fbf1c7",
            "panelAlt": "#f2e5bc",
            "border": "#d5c4a1",
            "accent": "#af3a03",
            "accentMuted": "#b57614",
            "text": "#3c3836",
            "muted": "#7c6f64",
            "addedBg": "#e6e3bb",
            "removedBg": "#f1d6bf",
            "contextBg": "#f2e5bc",
            "addedContentBg": "#dddfb3",
            "removedContentBg": "#ecc9b3",
            "contextContentBg": "#fbf1c7",
            "addedSignColor": "#79740e",
            "removedSignColor": "#9d0006",
            "lineNumberBg": "#f2e5bc",
            "lineNumberFg": "#928374",
            "selectedHunk": "#ebdbb2",
            "badgeAdded": "#79740e",
            "badgeRemoved": "#9d0006",
            "badgeNeutral": "#7c6f64",
            "fileNew": "#79740e",
            "fileDeleted": "#9d0006",
            "fileRenamed": "#076678",
            "fileModified": "#b57614",
            "fileUntracked": "#8f3f71",
            "noteBorder": "#b57614",
            "noteBackground": "#f2e5bc",
            "noteTitleBackground": "#ebdbb2",
            "noteTitleText": "#3c3836",
        },
        "syntax": {
            "default": "#3c3836",
            "keyword": "#9d0006",
            "string": "#79740e",
            "comment": "#928374",
            "number": "#8f3f71",
            "function": "#b57614",
            "property": "#076678",
            "type": "#427b58",
            "punctuation": "#665c54",
        },
    },
    Mode.DARK: {
        "custom_theme": {
            "label": "Gruvbox Dark Hard",
            "background": "#1d2021",
            "panel": "#282828",
            "panelAlt": "#32302f",
            "border": "#504945",
            "accent": "#fe8019",
            "accentMuted": "#d65d0e",
            "text": "#ebdbb2",
            "muted": "#a89984",
            "addedBg": "#2d331f",
            "removedBg": "#3c1f1e",
            "contextBg": "#282828",
            "addedContentBg": "#343b22",
            "removedContentBg": "#4a2725",
            "contextContentBg": "#32302f",
            "addedSignColor": "#b8bb26",
            "removedSignColor": "#fb4934",
            "lineNumberBg": "#282828",
            "lineNumberFg": "#928374",
            "selectedHunk": "#3c3836",
            "badgeAdded": "#98971a",
            "badgeRemoved": "#cc241d",
            "badgeNeutral": "#928374",
            "fileNew": "#b8bb26",
            "fileDeleted": "#fb4934",
            "fileRenamed": "#83a598",
            "fileModified": "#fabd2f",
            "fileUntracked": "#d3869b",
            "noteBorder": "#d65d0e",
            "noteBackground": "#32302f",
            "noteTitleBackground": "#3c3836",
            "noteTitleText": "#ebdbb2",
        },
        "syntax": {
            "default": "#ebdbb2",
            "keyword": "#fb4934",
            "string": "#b8bb26",
            "comment": "#928374",
            "number": "#d3869b",
            "function": "#fabd2f",
            "property": "#83a598",
            "type": "#8ec07c",
            "punctuation": "#a89984",
        },
    },
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
