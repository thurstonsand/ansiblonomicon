#!/usr/bin/env python3
"""Establish pod042's one-time password bridge, then run native bootstrap."""

import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import NoReturn, cast

ROOT = Path(__file__).resolve().parent.parent
RECONCILE = ROOT / "scripts" / "pod042_reconcile.py"
USER = "thurstonsand"
VAULT = "agent"
ITEM = "pod042"
SUDOERS = "/etc/sudoers.d/thurstonsand"
OPERATOR_PUBLIC_KEY = (
    ROOT / "bootstrap" / "targets" / "pod042" / "base" / "files" / "operator.pub"
)
IDENTITY_AGENT_ENV = "POD042_SSH_IDENTITY_AGENT"


class FirstAccessError(Exception):
    pass


def fail(message: str) -> NoReturn:
    raise FirstAccessError(message)


def command(
    argv: list[str],
    *,
    check: bool = True,
    capture_output: bool = False,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=check,
        capture_output=capture_output,
        input=input_text,
        env=env,
        text=True,
    )


def replace_login_fields(item: dict[str, object], password: str) -> dict[str, object]:
    item["title"] = ITEM
    fields = item.get("fields")
    if not isinstance(fields, list):
        fail("1Password Login template has no fields")
    replacements = {"username": USER, "password": password}
    found: set[str] = set()
    for value in cast(list[object], fields):
        if not isinstance(value, dict):
            continue
        field = cast(dict[str, object], value)
        field_id = field.get("id")
        if isinstance(field_id, str) and field_id in replacements:
            field["value"] = replacements[field_id]
            found.add(field_id)
    missing = replacements.keys() - found
    if missing:
        fail(f"1Password Login template lacks fields: {', '.join(sorted(missing))}")
    return item


def password_item() -> tuple[dict[str, object], bool]:
    existing = command(
        [
            "op",
            "item",
            "get",
            ITEM,
            "--vault",
            VAULT,
            "--format=json",
            "--reveal",
        ],
        check=False,
        capture_output=True,
    )
    if existing.returncode == 0:
        item = cast(dict[str, object], json.loads(existing.stdout))
        return item, True
    template = command(["op", "item", "template", "get", "Login"], capture_output=True)
    item = cast(dict[str, object], json.loads(template.stdout))
    return item, False


def store_password(password: str) -> None:
    item, exists = password_item()
    payload = json.dumps(replace_login_fields(item, password))
    if exists:
        item_id = item.get("id")
        if not isinstance(item_id, str):
            fail("existing pod042 Login item has no ID")
        argv = ["op", "item", "edit", item_id, "--vault", VAULT]
    else:
        argv = ["op", "item", "create", "--vault", VAULT, "-"]
    command(argv, capture_output=True, input_text=payload)


def install_key(host: str, password: str) -> None:
    environment = {**os.environ, "SSHPASS": password}
    command(
        [
            "sshpass",
            "-e",
            "ssh-copy-id",
            "-f",
            "-i",
            str(OPERATOR_PUBLIC_KEY),
            "-o",
            "StrictHostKeyChecking=accept-new",
            f"{USER}@{host}",
        ],
        env=environment,
    )


def key_only_ssh(host: str, *argv: str) -> list[str]:
    command = [
        "ssh",
        "-i",
        str(OPERATOR_PUBLIC_KEY),
        "-o",
        "BatchMode=yes",
        "-o",
        "IdentitiesOnly=yes",
    ]
    if identity_agent := os.environ.get(IDENTITY_AGENT_ENV):
        command.extend(["-o", f"IdentityAgent={identity_agent}"])
    return [*command, f"{USER}@{host}", *argv]


def establish_passwordless_sudo(host: str, password: str) -> None:
    install = (
        "umask 022; "
        f"printf '%s\\n' '{USER} ALL=(ALL:ALL) NOPASSWD: ALL' > {SUDOERS}; "
        f"chmod 0440 {SUDOERS}; visudo -cf {SUDOERS}"
    )
    command(
        key_only_ssh(host, "sudo", "-S", "-p", "", "sh", "-c", install),
        input_text=f"{password}\n",
    )


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="Fresh Debian address or resolvable name")
    parser.add_argument(
        "--replace-host-key",
        action="store_true",
        help="Forget the prior SSH host key before connecting",
    )
    args = parser.parse_args(argv)
    password = getpass.getpass(f"Temporary Debian password for {USER}: ")
    if not password:
        fail("password cannot be empty")
    store_password(password)
    if args.replace_host_key:
        command(["ssh-keygen", "-R", args.host], check=False)
    install_key(args.host, password)
    command(key_only_ssh(args.host, "true"))
    establish_passwordless_sudo(args.host, password)
    command(
        [
            sys.executable,
            str(RECONCILE),
            "--host",
            args.host,
            "--initial",
        ]
    )
    command(key_only_ssh(args.host, "true"))
    return 0


def main() -> int:
    try:
        return run(sys.argv[1:])
    except (
        FirstAccessError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as error:
        print(f"pod042 first access: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
