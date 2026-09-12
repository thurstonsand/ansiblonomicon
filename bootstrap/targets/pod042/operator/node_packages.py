#!/usr/bin/env python3
"""Install the operator's npm inventory with the npm beside a given Node.

Usage: node_packages.py <npm>

Both call sites pass their own npm: the node tool's postinstall hook uses the one it just
installed, and operator:tools uses whichever Node mise currently selects.
"""

import os
from pathlib import Path
import subprocess
import sys
import tomllib

INVENTORY = Path(__file__).with_name("node-packages.toml")


def run(*command: str, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True, env=env)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: node_packages.py <npm>")
    npm = sys.argv[1]
    inventory = tomllib.loads(INVENTORY.read_text())

    packages: list[str] = inventory["global"]["packages"]
    allow_scripts: list[str] = inventory["global"]["allow_scripts"]
    run(npm, "install", "-g", f"--allow-scripts={','.join(allow_scripts)}", *packages)

    for name, entry in inventory["prefixed"].items():
        env = os.environ | {"NPM_CONFIG_USERCONFIG": entry["npmrc"]}
        run(
            npm,
            "install",
            "--prefix",
            entry["prefix"],
            "--no-audit",
            "--no-fund",
            entry["spec"],
            env=env,
        )
        link = Path(entry["link"])
        link.unlink(missing_ok=True)
        link.symlink_to(Path(entry["prefix"]) / "node_modules/.bin" / name)


if __name__ == "__main__":
    main()
