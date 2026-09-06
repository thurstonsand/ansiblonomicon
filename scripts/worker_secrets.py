"""Canonical secret bindings shared by Worker deployment and local development."""

import os
from pathlib import Path

WORKER_BINDINGS = {
    "aig": {
        "API_KEY": "CLI_PROXY_API_KEY",
        "AIG_TOKEN": "CLOUDFLARE_AI_GATEWAY_API_TOKEN",
        "CF_ACCESS_CLIENT_ID": "CF_ACCESS_CLIENT_ID",
        "CF_ACCESS_CLIENT_SECRET": "CF_ACCESS_CLIENT_SECRET",
    },
    "hooks": {
        "GOG_GMAIL_TOKEN": "GOG_GMAIL_PUSH_TOKEN",
        "OPENCLAW_HOOKS_TOKEN": "OPENCLAW_HOOKS_TOKEN",
        "OPENCLAW_GATEWAY_TOKEN": "OPENCLAW_GATEWAY_TOKEN",
        "TELEGRAM_WEBHOOK_SECRET": "TELEGRAM_WEBHOOK_SECRET",
        "ELEVENLABS_VOICE_TOKEN": "ELEVENLABS_VOICE_TOKEN",
    },
}


def required_secrets(worker: str) -> dict[str, str]:
    bindings = WORKER_BINDINGS[worker]
    missing = [source for source in bindings.values() if not os.environ.get(source)]
    if missing:
        raise ValueError(
            f"Missing required Worker environment values: {', '.join(missing)}"
        )
    return {name: os.environ[source] for name, source in bindings.items()}


def reject_dev_vars(worker_dir: Path) -> None:
    if list(worker_dir.glob(".dev.vars*")):
        raise ValueError(
            f"Remove stale .dev.vars files from {worker_dir} before proceeding"
        )
