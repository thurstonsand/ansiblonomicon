#!/usr/bin/env python3
"""Deploy aig Worker via Wrangler with secret management.

Secrets are supplied through the canonical fnox environment.
Use --force-secret/-f to update secrets even if they exist.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from worker_secrets import reject_dev_vars, required_secrets

ROOT_DIR = Path(__file__).parent.parent
WORKER_DIR = ROOT_DIR / "wrangler" / "aig"


def get_existing_secrets() -> set[str]:
    result = subprocess.run(
        ["wrangler", "secret", "list", "--format", "json"],
        cwd=WORKER_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    return {s["name"] for s in json.loads(result.stdout)}


def main(force_secret: bool) -> int:
    try:
        secrets = required_secrets("aig")
        reject_dev_vars(WORKER_DIR)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print("Deploying aig worker...")
    subprocess.run(["wrangler", "deploy"], cwd=WORKER_DIR, check=True)

    print("\nChecking secrets...")
    existing = get_existing_secrets()

    for name, value in secrets.items():
        if name in existing:
            if force_secret:
                print(f"Updating {name} secret (-f)...")
                subprocess.run(
                    ["wrangler", "secret", "put", name],
                    cwd=WORKER_DIR,
                    input=value,
                    text=True,
                    check=True,
                )
            else:
                print(f"{name} secret already exists (use -f to update)")
        else:
            print(f"Creating {name} secret...")
            subprocess.run(
                ["wrangler", "secret", "put", name],
                cwd=WORKER_DIR,
                input=value,
                text=True,
                check=True,
            )

    print("\nDone! Worker deployed to https://aig.thurstons.house")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Deploy the aig Worker via Wrangler with secret management."
    )
    _ = parser.add_argument(
        "--force-secret",
        "-f",
        action="store_true",
        help="Update secrets even if they exist",
    )
    args = parser.parse_args()
    sys.exit(main(args.force_secret))
