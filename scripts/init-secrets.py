#!/usr/bin/env python3
"""Resolve 1Password secrets from .secrets.jsonc and cache to .env.secrets."""

from datetime import UTC, datetime
from pathlib import Path
import subprocess
import sys

import jsonc  # pyright: ignore[reportMissingTypeStubs]

ROOT_DIR = Path(__file__).parent.parent
SECRETS_CONFIG = ROOT_DIR / ".secrets.jsonc"
SECRETS_CACHE = ROOT_DIR / ".env.secrets"


def resolve_secret(value: str) -> str:
    """Resolve op:// references via 1Password CLI, or return literal values."""
    if not value.startswith("op://"):
        return value

    result = subprocess.run(
        ["op", "read", value],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"Error resolving {value}: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def main() -> None:
    # Check if cache is current
    if (
        SECRETS_CACHE.exists()
        and SECRETS_CACHE.stat().st_mtime > SECRETS_CONFIG.stat().st_mtime
    ):
        print("Secrets cache is current.")
        return

    if not SECRETS_CONFIG.exists():
        print(f"Error: {SECRETS_CONFIG} not found", file=sys.stderr)
        sys.exit(1)

    print("Resolving secrets from 1Password (one-time auth)...")

    config: dict[str, str] = jsonc.loads(SECRETS_CONFIG.read_text())
    resolved: dict[str, str] = {}

    for key, value in config.items():
        resolved[key] = resolve_secret(value)

    lines = [
        "# Cached secrets - DO NOT COMMIT",
        f"# Generated: {datetime.now(UTC).isoformat()}",
        "# Source: .secrets.jsonc",
        "# Regenerate: poe init-secrets",
        "",
    ]
    for key, value in resolved.items():
        # Escape any double quotes in the value
        escaped = value.replace('"', '\\"')
        lines.append(f'{key}="{escaped}"')

    SECRETS_CACHE.write_text("\n".join(lines) + "\n")
    SECRETS_CACHE.chmod(0o600)

    print(f"Secrets cached to .env.secrets ({len(resolved)} vars, mode 600)")


if __name__ == "__main__":
    main()
