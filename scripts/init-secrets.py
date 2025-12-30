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

    # Build a template for op inject to resolve all secrets in one call
    # Format: KEY="{{ op://... }}" for op:// refs, KEY="literal" for literals
    template_lines: list[str] = []
    for key, value in config.items():
        if value.startswith("op://"):
            # Use op inject template syntax: {{ op://vault/item/field }}
            template_lines.append(f'{key}={{{{ {value} }}}}')
        else:
            # Literal value - escape any braces and quotes
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            template_lines.append(f'{key}="{escaped}"')

    template = "\n".join(template_lines)

    # Run op inject to resolve all secrets at once
    result = subprocess.run(
        ["op", "inject"],
        input=template,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        print(f"Error resolving secrets: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    # Parse resolved output and build final .env file
    resolved_lines = result.stdout.strip().split("\n")
    lines = [
        "# Cached secrets - DO NOT COMMIT",
        f"# Generated: {datetime.now(UTC).isoformat()}",
        "# Source: .secrets.jsonc",
        "# Regenerate: poe init-secrets",
        "",
    ]

    for line in resolved_lines:
        if "=" in line:
            key, value = line.split("=", 1)
            # Ensure values are quoted
            if not (value.startswith('"') and value.endswith('"')):
                value = f'"{value.replace(chr(34), chr(92) + chr(34))}"'
            lines.append(f"{key}={value}")

    SECRETS_CACHE.write_text("\n".join(lines) + "\n")
    SECRETS_CACHE.chmod(0o600)

    print(f"Secrets cached to .env.secrets ({len(config)} vars, mode 600)")


if __name__ == "__main__":
    main()
