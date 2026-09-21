#!/usr/bin/env python3
"""Reconcile the personal Mac's persisted pod042 Docker context."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import cast

NAME = "pod042"
HOST = "ssh://pod042"
DESCRIPTION = "pod042 Debian NAS over SSH"


def parse_context(payload: str) -> tuple[str | None, str | None]:
    decoded: object = json.loads(payload)
    if not isinstance(decoded, list):
        raise ValueError
    items = cast(list[object], decoded)
    if len(items) != 1:
        raise ValueError
    state = items[0]
    if not isinstance(state, dict):
        raise ValueError
    state = cast(dict[str, object], state)
    if state.get("Name") != NAME:
        raise ValueError
    metadata = state.get("Metadata")
    endpoints = state.get("Endpoints")
    if not isinstance(metadata, dict) or not isinstance(endpoints, dict):
        raise ValueError
    metadata = cast(dict[str, object], metadata)
    endpoints = cast(dict[str, object], endpoints)
    docker = endpoints.get("docker")
    if "docker" in endpoints and not isinstance(docker, dict):
        raise ValueError
    docker_endpoint = cast(
        dict[str, object], docker if isinstance(docker, dict) else {}
    )
    description = metadata.get("Description")
    host = docker_endpoint.get("Host")
    if ("Description" in metadata and not isinstance(description, str)) or (
        "Host" in docker_endpoint and not isinstance(host, str)
    ):
        raise ValueError
    return (
        description if isinstance(description, str) else None,
        host if isinstance(host, str) else None,
    )


def docker(
    environment: dict[str, str], *arguments: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *arguments],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    environment = os.environ.copy()
    environment.pop("DOCKER_HOST", None)
    environment.pop("DOCKER_CONTEXT", None)
    if shutil.which("docker", path=environment.get("PATH")) is None:
        print("docker is required to reconcile the pod042 context", file=sys.stderr)
        return 1

    inspected = docker(environment, "context", "inspect", NAME)
    missing = False
    actual = (None, None)
    if inspected.returncode:
        listed = docker(environment, "context", "ls", "--format", "{{.Name}}")
        if listed.returncode:
            print(
                listed.stderr or "failed to list Docker contexts",
                file=sys.stderr,
                end="",
            )
            return listed.returncode
        if NAME in listed.stdout.splitlines():
            print(
                inspected.stderr or f"failed to inspect Docker context {NAME}\n",
                file=sys.stderr,
                end="",
            )
            return inspected.returncode
        missing = True
    else:
        try:
            actual = parse_context(inspected.stdout)
        except ValueError:
            print(f"Docker returned invalid context data for {NAME}", file=sys.stderr)
            return 1

    needs_fields = missing or actual != (DESCRIPTION, HOST)
    shown = docker(environment, "context", "show")
    if shown.returncode:
        print(
            shown.stderr or "failed to read the current Docker context",
            file=sys.stderr,
            end="",
        )
        return shown.returncode
    needs_use = shown.stdout.strip() != NAME

    if args.check:
        if missing:
            print(f"Docker context would be created: {NAME}", file=sys.stderr)
        elif needs_fields:
            print(f"Docker context would be updated: {NAME}", file=sys.stderr)
        if needs_use:
            print(f"Docker context would be selected: {NAME}", file=sys.stderr)
        return 0

    if needs_fields:
        action = "create" if missing else "update"
        changed = docker(
            environment,
            "context",
            action,
            NAME,
            "--description",
            DESCRIPTION,
            "--docker",
            f"host={HOST}",
        )
        if changed.returncode:
            print(changed.stderr, file=sys.stderr, end="")
            return changed.returncode
    if needs_use:
        selected = docker(environment, "context", "use", NAME)
        if selected.returncode:
            print(selected.stderr, file=sys.stderr, end="")
            return selected.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
