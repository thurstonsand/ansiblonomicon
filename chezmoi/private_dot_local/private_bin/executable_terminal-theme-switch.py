"""Applies side effects when the terminal switches between dark and light mode.

Called by tmux hooks (Mode 2031) and zsh helper functions.
"""

import json
from pathlib import Path
import sys
from typing import Literal

Mode = Literal["dark", "light"]
VALID_MODES: set[Mode] = {"dark", "light"}


def update_terminal_bg(mode: Mode) -> None:
    Path.home().joinpath(".terminal-bg").write_text(mode + "\n")


def update_claude_theme(mode: Mode) -> None:
    claude_json = Path.home() / ".claude.json"
    if not claude_json.exists():
        return
    config: dict[str, object] = json.loads(claude_json.read_text())
    config["theme"] = mode
    claude_json.write_text(json.dumps(config, indent=2) + "\n")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in VALID_MODES:
        print(f"Usage: python3 {sys.argv[0]} <dark|light>", file=sys.stderr)
        sys.exit(1)

    mode: Mode = sys.argv[1]  # type: ignore[assignment]
    update_terminal_bg(mode)
    update_claude_theme(mode)


if __name__ == "__main__":
    main()
