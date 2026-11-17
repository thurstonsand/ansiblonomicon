"""Render the librarian command that Claude Code and Codex share with Pi's installed copy."""

from pathlib import Path
import subprocess
from typing import Any

WORK_HOST = "ML-DFC6YK6VJQ"


# Pi only installs a missing package and never updates one on its own, so the reconcile keeps
# the copy Claude Code and Codex run on the librarian's latest release.
def update(home: Path, hostname: str) -> None:
    source = (
        "git:github.com/thurstonsand/pi-librarian@downgrade"
        if hostname == WORK_HOST
        else "npm:@thurstonsand/pi-librarian"
    )
    subprocess.run(
        [
            "mise",
            "-C",
            str(home),
            "exec",
            "--",
            "pi",
            "update",
            "--extension",
            source,
            "--no-approve",
        ],
        check=True,
    )


# Pi installs the librarian package, so the other harnesses run that same copy rather than a
# second install that the work mirror may not serve.
def cli(home: Path, hostname: str) -> Path:
    package = (
        home / ".pi/agent/git/github.com/thurstonsand/pi-librarian"
        if hostname == WORK_HOST
        else home / ".pi/agent/npm/node_modules/@thurstonsand/pi-librarian"
    )
    path = package / "dist/cli/librarian.js"
    if not path.is_file():
        raise ValueError(
            f"{path} is missing; start pi once so it installs pi-librarian"
        )
    return path


# Claude Code appends its plugins' bin directories to PATH, so this command shadows the plugin's
# own, which runs the CLI through npx.
def render(
    *,
    repo: Path,
    home: Path,
    hostname: str,
    data: dict[str, Any],
    secrets: dict[str, str],
) -> dict[str, str]:
    del repo, data, secrets
    return {
        ".local/bin/librarian": f'''#!/usr/bin/env bash
set -euo pipefail
exec "$(mise which -C "{home}" node)" "{cli(home, hostname)}" "$@"
'''
    }
