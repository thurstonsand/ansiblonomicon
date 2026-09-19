#!/usr/bin/env python3
"""Install the Mac npm inventory using the npm supplied by the caller."""

import argparse
from pathlib import Path
import subprocess

from reconcile import load


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--present", action="store_true")
    parser.add_argument("npm")
    parser.add_argument("inventories", nargs="+", type=Path)
    args = parser.parse_args()
    inventory = load(args.inventories)
    packages = inventory.sections["npm"]["packages"]
    allowed = inventory.sections["npm"]["allow_scripts"]
    if packages:
        allow_scripts = ",".join(sorted(set(allowed)))
        current = subprocess.run(
            [args.npm, "config", "get", "allow-scripts", "--location=user"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        if current != allow_scripts:
            subprocess.run(
                [
                    args.npm,
                    "config",
                    "set",
                    f"allow-scripts={allow_scripts}",
                    "--location=user",
                ],
                check=True,
            )
        if args.present:
            packages = [
                package
                for package in packages
                if subprocess.run(
                    [args.npm, "list", "-g", "--depth=0", package],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                ).returncode
                != 0
            ]
        if packages:
            subprocess.run(
                [
                    args.npm,
                    "install",
                    "-g",
                    f"--allow-scripts={allow_scripts}",
                    *packages,
                ],
                check=True,
            )


if __name__ == "__main__":
    main()
