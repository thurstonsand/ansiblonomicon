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
PERSONAL_OP_ACCOUNT_PREFIX = "PQ7X5"
WORK_OP_ACCOUNT_PREFIX = "EU7WV"
PERSONAL_HOSTNAME = "Thurstons-MacBook-Pro"
WORK_HOSTNAME = "ML-DFC6YK6VJQ"
MACHINE_SECRET_KEYS = {
    "ANTHROPIC_AUTH_TOKEN": {WORK_HOSTNAME},
    "BITBUCKET_TOKEN": {WORK_HOSTNAME},
    "GITLAB_ACCESS_TOKEN": {WORK_HOSTNAME},
    "HOMEBREW_SUDO_ASKPASS_PASS": {PERSONAL_HOSTNAME},
    "HOMEBREW_SUDO_ASKPASS_PASS_WORK": {WORK_HOSTNAME},
    "LOGSCALE_VIPER_SPOG_TOKEN": {WORK_HOSTNAME},
    "N8N_API_KEY": {WORK_HOSTNAME},
    "SOURCEGRAPH_TOKEN": {WORK_HOSTNAME},
}
SECRET_ACCOUNT_PREFIXES = {
    "ANTHROPIC_AUTH_TOKEN": WORK_OP_ACCOUNT_PREFIX,
    "BITBUCKET_TOKEN": WORK_OP_ACCOUNT_PREFIX,
    "GITLAB_ACCESS_TOKEN": WORK_OP_ACCOUNT_PREFIX,
    "LOGSCALE_VIPER_SPOG_TOKEN": WORK_OP_ACCOUNT_PREFIX,
    "N8N_API_KEY": WORK_OP_ACCOUNT_PREFIX,
    "SOURCEGRAPH_TOKEN": WORK_OP_ACCOUNT_PREFIX,
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


def uses_service_account() -> bool:
    return service_account_op_wrapper() is not None or (
        os.environ.get("AMP_ORB") == "1"
        and bool(os.environ.get("OP_SERVICE_ACCOUNT_TOKEN"))
    )


def secrets_for_hostname(config: dict[str, str], hostname: str) -> dict[str, str]:
    return {
        key: value
        for key, value in config.items()
        if key not in MACHINE_SECRET_KEYS or hostname in MACHINE_SECRET_KEYS[key]
    }


def op_environment() -> dict[str, str]:
    env = os.environ.copy()
    if not uses_service_account():
        env.pop("OP_SERVICE_ACCOUNT_TOKEN", None)
    return env


def resolve_op_accounts(prefixes: set[str]) -> dict[str, str | None]:
    if uses_service_account():
        return dict.fromkeys(prefixes)

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
    resolved: dict[str, str | None] = {}
    for prefix in prefixes:
        account = next(
            (
                account["account_uuid"]
                for account in accounts
                if account["account_uuid"].startswith(prefix)
            ),
            None,
        )
        if account is None:
            print(f"No 1Password account matching prefix {prefix}", file=sys.stderr)
            sys.exit(1)
        resolved[prefix] = account
    return resolved


def resolve_secrets(config: dict[str, str]) -> dict[str, str | None]:
    grouped: dict[str, dict[str, str]] = {}
    for key, value in config.items():
        prefix = SECRET_ACCOUNT_PREFIXES.get(key, PERSONAL_OP_ACCOUNT_PREFIX)
        grouped.setdefault(prefix, {})[key] = value

    accounts = resolve_op_accounts(set(grouped))
    resolved: dict[str, str | None] = {}
    for prefix, secrets in grouped.items():
        template_lines: list[str] = []
        for key, value in secrets.items():
            if value.startswith("op://"):
                template_lines.append(f"{key}={{{{ {value} }}}}")
            else:
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                template_lines.append(f'{key}="{escaped}"')

        command = [op_command(), "inject"]
        if account := accounts[prefix]:
            command.extend(["--account", account])
        result = subprocess.run(
            command,
            input="\n".join(template_lines),
            capture_output=True,
            text=True,
            check=False,
            env=op_environment(),
        )
        if result.returncode != 0:
            print(f"Error resolving secrets: {result.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
        resolved.update(dotenv_values(stream=StringIO(result.stdout)))

    return resolved


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

    resolved_secrets = resolve_secrets(config)

    # Build final .env file
    lines = [
        "# Cached secrets - DO NOT COMMIT",
        f"# Generated: {datetime.now(UTC).isoformat()}",
        "# Source: .secrets.jsonc",
        "# Regenerate: mise run secrets:init",
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
            "# Regenerate: mise run secrets:init",
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
