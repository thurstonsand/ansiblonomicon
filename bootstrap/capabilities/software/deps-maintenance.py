#!/usr/bin/env python3
"""Maintain Go module dependencies on a daily successful-run cadence."""

import argparse
import os
from pathlib import Path
import subprocess
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("stamp", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    due = not args.stamp.exists() or time.time() - args.stamp.stat().st_mtime >= 86400
    if not due:
        return 0
    if args.check:
        print(f"Go dependency maintenance is due: {args.source}")
        return 0

    env = {
        **os.environ,
        "MISE_CEILING_PATHS": str(args.source.parent),
        "MISE_TRUSTED_CONFIG_PATHS": os.pathsep.join(
            filter(
                None, (os.environ.get("MISE_TRUSTED_CONFIG_PATHS"), str(args.source))
            )
        ),
    }
    subprocess.run(
        ["mise", "run", "--skip-tools", "deps:update"],
        cwd=args.source,
        env=env,
        check=True,
    )
    args.stamp.parent.mkdir(parents=True, exist_ok=True)
    args.stamp.touch(mode=0o644)
    args.stamp.chmod(0o644)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
