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
    "home-assistant-headers": "HOMEASSISTANT_MCP_TOKEN",
}


def secret(name: str) -> str:
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["cloudflare-api", *HEADER_SECRETS])
    args = parser.parse_args()
    if args.mode in HEADER_SECRETS:
        token = secret(HEADER_SECRETS[args.mode])
        print(json.dumps({"Authorization": f"Bearer {token}"}))
        return
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
    environment["CLOUDFLARE_API_TOKEN"] = secret("CLOUDFLARE_API_TOKEN")
    command = [
        "mise",
        "-C",
        str(ROOT),
        "exec",
        "--",
        "mcp-remote",
        "https://mcp.cloudflare.com/mcp",
        "--header",
        "Authorization:Bearer ${CLOUDFLARE_API_TOKEN}",
    ]
    os.execvpe(command[0], command, environment)


if __name__ == "__main__":
    main()
