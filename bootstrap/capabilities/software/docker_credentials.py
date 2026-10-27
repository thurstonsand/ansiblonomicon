#!/usr/bin/env python3
"""Reconcile the work Artifactory identity in Docker's credential store."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import cast


def credential_helper(registry: str) -> str:
    config_dir = Path(os.environ.get("DOCKER_CONFIG", Path.home() / ".docker"))
    decoded: object = json.loads((config_dir / "config.json").read_text())
    if not isinstance(decoded, dict):
        raise ValueError("Docker config must be a JSON object")
    config = cast(dict[str, object], decoded)
    helpers = config.get("credHelpers", {})
    if not isinstance(helpers, dict):
        raise ValueError("Docker credHelpers must be an object")
    store = cast(dict[str, object], helpers).get(registry, config.get("credsStore"))
    if not isinstance(store, str) or not store:
        raise ValueError(f"Docker config names no credential store for {registry}")
    return f"docker-credential-{store}"


def stored_identity(helper: str, registry: str) -> tuple[str, str] | None:
    result = subprocess.run(
        [helper, "get"], input=registry, text=True, capture_output=True, check=False
    )
    if result.returncode:
        if "credentials not found" in result.stdout + result.stderr:
            return None
        raise RuntimeError(result.stderr or result.stdout or f"{helper} get failed")
    decoded: object = json.loads(result.stdout)
    if not isinstance(decoded, dict):
        raise ValueError(f"{helper} returned invalid credentials for {registry}")
    stored = cast(dict[str, object], decoded)
    username = stored.get("Username")
    secret = stored.get("Secret")
    if not isinstance(username, str) or not isinstance(secret, str):
        raise ValueError(f"{helper} returned invalid credentials for {registry}")
    return username, secret


def store_identity(helper: str, registry: str, identity: tuple[str, str]) -> None:
    payload = {"ServerURL": registry, "Username": identity[0], "Secret": identity[1]}
    subprocess.run([helper, "store"], input=json.dumps(payload), text=True, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registries", nargs="+")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        for registry in args.registries:
            if stored_identity(credential_helper(registry), registry) is None:
                print(f"Docker credential would be stored: {registry}", file=sys.stderr)
        return 0

    identity = (
        os.environ["ARTIFACTORY_USERNAME"],
        os.environ["ARTIFACTORY_IDENTITY_TOKEN"],
    )
    for registry in args.registries:
        helper = credential_helper(registry)
        if stored_identity(helper, registry) != identity:
            store_identity(helper, registry, identity)
            print(f"Docker credential updated: {registry}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
