#!/usr/bin/env python3
"""Resolve 1Password secrets from .secrets.jsonc and cache to .env.

Also generates .dev.vars files for Cloudflare Workers based on WORKER_DEV_VARS mapping.
"""

from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
import subprocess
import sys

from dotenv import dotenv_values
import jsonc  # pyright: ignore[reportMissingTypeStubs]

ROOT_DIR = Path(__file__).parent.parent
SECRETS_CONFIG = ROOT_DIR / ".secrets.jsonc"
SECRETS_CACHE = ROOT_DIR / ".env"

# Map worker directories to their .dev.vars secrets
# Format: { "worker/path": { "WORKER_VAR": "ENV_VAR_NAME" } }
WORKER_DEV_VARS: dict[str, dict[str, str]] = {
    "wrangler/aig": {
        "API_KEY": "CLI_PROXY_API_KEY",
        "AIG_TOKEN": "CLOUDFLARE_AI_GATEWAY_API_TOKEN",
        "CF_ACCESS_CLIENT_ID": "CF_ACCESS_CLIENT_ID",
        "CF_ACCESS_CLIENT_SECRET": "CF_ACCESS_CLIENT_SECRET",
    },
}


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
            template_lines.append(f"{key}={{{{ {value} }}}}")
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

    # Parse resolved output
    resolved_secrets = dotenv_values(stream=StringIO(result.stdout))

    # Build final .env file
    lines = [
        "# Cached secrets - DO NOT COMMIT",
        f"# Generated: {datetime.now(UTC).isoformat()}",
        "# Source: .secrets.jsonc",
        "# Regenerate: poe init-secrets",
        "",
    ]
    for key, value in resolved_secrets.items():
        escaped = (value or "").replace('"', '\\"')
        lines.append(f'{key}="{escaped}"')

    SECRETS_CACHE.write_text("\n".join(lines) + "\n")
    SECRETS_CACHE.chmod(0o600)

    print(f"Secrets cached to .env ({len(config)} vars, mode 600)")

    # Generate .dev.vars for workers
    for worker_path, var_mapping in WORKER_DEV_VARS.items():
        dev_vars_path = ROOT_DIR / worker_path / ".dev.vars"
        dev_vars_lines = [
            "# Cached secrets for local development - DO NOT COMMIT",
            f"# Generated: {datetime.now(UTC).isoformat()}",
            "# Regenerate: poe init-secrets",
            "",
        ]
        for worker_var, env_var in var_mapping.items():
            value = resolved_secrets.get(env_var, "")
            dev_vars_lines.append(f'{worker_var}="{value}"')

        dev_vars_path.write_text("\n".join(dev_vars_lines) + "\n")
        dev_vars_path.chmod(0o600)
        print(f"Generated {worker_path}/.dev.vars ({len(var_mapping)} vars)")


if __name__ == "__main__":
    main()
