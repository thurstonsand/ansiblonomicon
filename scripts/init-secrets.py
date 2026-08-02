#!/usr/bin/env python3
"""Resolve 1Password secrets from .secrets.jsonc and cache to .env.

Also generates .dev.vars files for Cloudflare Workers based on WORKER_DEV_VARS mapping.
"""

from datetime import UTC, datetime
from io import StringIO
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

from dotenv import dotenv_values
import jsonc  # pyright: ignore[reportMissingTypeStubs]

ROOT_DIR = Path(__file__).parent.parent
SECRETS_CONFIG = ROOT_DIR / ".secrets.jsonc"
SECRETS_CACHE = ROOT_DIR / ".env"
OP_ACCOUNT_PREFIX = "PQ7X5"
PERSONAL_HOSTNAME = "Thurstons-MacBook-Pro"
WORK_HOSTNAME = "ML-DFC6YK6VJQ"
MACHINE_SECRET_KEYS = {
    "HOMEBREW_SUDO_ASKPASS_PASS": {PERSONAL_HOSTNAME},
    "HOMEBREW_SUDO_ASKPASS_PASS_WORK": {WORK_HOSTNAME},
}

# Map worker directories to their .dev.vars secrets
# Format: { "worker/path": { "WORKER_VAR": "ENV_VAR_NAME" } }
WORKER_DEV_VARS: dict[str, dict[str, str]] = {
    "wrangler/aig": {
        "API_KEY": "CLI_PROXY_API_KEY",
        "AIG_TOKEN": "CLOUDFLARE_AI_GATEWAY_API_TOKEN",
        "CF_ACCESS_CLIENT_ID": "CF_ACCESS_CLIENT_ID",
        "CF_ACCESS_CLIENT_SECRET": "CF_ACCESS_CLIENT_SECRET",
    },
    "wrangler/hooks": {
        "GOG_GMAIL_TOKEN": "GOG_GMAIL_PUSH_TOKEN",
        "OPENCLAW_HOOKS_TOKEN": "OPENCLAW_HOOKS_TOKEN",
        "OPENCLAW_GATEWAY_TOKEN": "OPENCLAW_GATEWAY_TOKEN",
        "TELEGRAM_WEBHOOK_SECRET": "TELEGRAM_WEBHOOK_SECRET",
        "ELEVENLABS_VOICE_TOKEN": "ELEVENLABS_VOICE_TOKEN",
    },
}


def service_account_op_wrapper() -> Path | None:
    wrapper = Path.home() / ".local/bin/op"
    if wrapper.exists():
        return wrapper
    return None


def op_command() -> str:
    wrapper = service_account_op_wrapper()
    return str(wrapper) if wrapper is not None else "op"


def secrets_for_hostname(config: dict[str, str], hostname: str) -> dict[str, str]:
    return {
        key: value
        for key, value in config.items()
        if key not in MACHINE_SECRET_KEYS or hostname in MACHINE_SECRET_KEYS[key]
    }


def op_environment() -> dict[str, str]:
    env = os.environ.copy()
    if service_account_op_wrapper() is None:
        env.pop("OP_SERVICE_ACCOUNT_TOKEN", None)
    return env


def resolve_op_account() -> str | None:
    if service_account_op_wrapper() is not None:
        return None

    result = subprocess.run(
        [op_command(), "account", "list", "--format=json"],
        capture_output=True,
        text=True,
        check=False,
        env=op_environment(),
    )
    if result.returncode != 0:
        print(
            f"Error listing 1Password accounts: {result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)
    accounts: list[dict[str, str]] = json.loads(result.stdout)
    for acct in accounts:
        if acct["account_uuid"].startswith(OP_ACCOUNT_PREFIX):
            return acct["account_uuid"]
    print(f"No 1Password account matching prefix {OP_ACCOUNT_PREFIX}", file=sys.stderr)
    sys.exit(1)


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

    hostname = socket.gethostname().split(".")[0]
    config: dict[str, str] = jsonc.loads(SECRETS_CONFIG.read_text())
    config = secrets_for_hostname(config, hostname)

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
    op_inject_cmd = [op_command(), "inject"]
    op_account = resolve_op_account()
    if op_account is not None:
        op_inject_cmd.extend(["--account", op_account])

    result = subprocess.run(
        op_inject_cmd,
        input=template,
        capture_output=True,
        text=True,
        check=False,
        env=op_environment(),
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
