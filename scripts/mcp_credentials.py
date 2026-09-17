#!/usr/bin/env python3
"""Resolve MCP credentials at connection time, without depending on agent startup."""

import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
HEADER_SECRETS = {
    "cloudflare-headers": "CLOUDFLARE_API_TOKEN",
    "home-assistant-headers": "HOMEASSISTANT_API_KEY",
}


def credential(name: str) -> str:
    result = subprocess.run(
        [str(ROOT / "scripts/fnox-host"), "get", name],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=10,
        check=True,
    ).stdout.strip()
    if not result:
        raise ValueError(f"{name} is empty")
    return result


def remote_environment(name: str, value: str) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        in {
            "PATH",
            "HOME",
            "TMPDIR",
            "SYSTEMROOT",
            "NODE_EXTRA_CA_CERTS",
            "SSL_CERT_FILE",
        }
    }
    environment[name] = value
    return environment


def exec_remote(endpoint: str, credential_name: str) -> None:
    command = [
        "mcp-remote",
        endpoint,
        "--header",
        f"Authorization:Bearer ${{{credential_name}}}",
    ]
    os.execvpe(
        command[0],
        command,
        remote_environment(credential_name, credential(credential_name)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=["cloudflare-api", *HEADER_SECRETS, "work-web-search"]
    )
    parser.add_argument("endpoint", nargs="?")
    args = parser.parse_args()
    if args.mode in HEADER_SECRETS:
        if args.endpoint:
            parser.error(f"{args.mode} does not accept an endpoint")
        token = credential(HEADER_SECRETS[args.mode])
        print(json.dumps({"Authorization": f"Bearer {token}"}))
        return
    if args.mode == "cloudflare-api":
        if args.endpoint:
            parser.error("cloudflare-api does not accept an endpoint")
        exec_remote("https://mcp.cloudflare.com/mcp", "CLOUDFLARE_API_TOKEN")
        return
    if not args.endpoint:
        parser.error("work-web-search requires an endpoint")
    exec_remote(args.endpoint, "ANTHROPIC_AUTH_TOKEN")


if __name__ == "__main__":
    main()
