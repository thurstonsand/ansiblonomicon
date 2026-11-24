"""Render the librarian command that Claude Code, Codex, and Antigravity share with Pi's installed copy."""

import json
from pathlib import Path
import subprocess
import tempfile
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


# The librarian writes its own role and rule, so they track its releases. It runs in an empty
# home: the codex settings arrive in a throwaway settings file, and the empty pi directory keeps
# its migration from moving the real pi settings.
def codex_setup(
    home: Path, cli_path: Path, codex: dict[str, str] | None = None
) -> dict[str, str]:
    node = subprocess.run(
        ["mise", "which", "-C", str(home), "node"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="librarian-role-") as temporary:
        root = Path(temporary)
        settings = root / "config/agents/librarian/config.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({"codex": codex} if codex else {}))
        subprocess.run(
            [node, str(cli_path), "codex", "setup"],
            check=True,
            capture_output=True,
            env={
                "HOME": str(root),
                "PATH": "",
                "CODEX_HOME": str(root / "codex"),
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_CACHE_HOME": str(root / "cache"),
                "XDG_STATE_HOME": str(root / "state"),
                "PI_CODING_AGENT_DIR": str(root / "pi"),
            },
        )
        return {
            relative: (root / "codex" / relative.removeprefix(".codex/")).read_text()
            for relative in (
                ".codex/agents/librarian.toml",
                ".codex/rules/librarian.rules",
            )
        }


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
