#!/usr/bin/env python3
"""Establish pod042's one-time password bridge, then run native bootstrap."""

import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
from typing import NoReturn, cast

from automation_identity import IdentityError, identity_path, read_identity

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


def op_command(
    argv: list[str], *, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        token = read_identity(identity_path(Path.home()), os.getuid())
    except FileNotFoundError:
        fail(
            "shared automation identity is missing; enroll it with "
            "mise --no-env exec -- python3 scripts/automation_identity.py"
        )
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("OP_", "FNOX_"))
    }
    environment["OP_SERVICE_ACCOUNT_TOKEN"] = token
    return command(
        ["op", *argv],
        capture_output=True,
        input_text=input_text,
        env=environment,
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
    listing = op_command(["item", "list", "--vault", VAULT, "--format=json"])
    entries = json.loads(listing.stdout)
    if not isinstance(entries, list):
        fail("1Password item list must be a list")
    matches: list[str] = []
    for raw_entry in cast(list[object], entries):
        if not isinstance(raw_entry, dict):
            fail("1Password item metadata must be an object")
        entry = cast(dict[str, object], raw_entry)
        if not isinstance(entry.get("title"), str):
            fail("1Password item metadata has no title")
        if entry["title"] == ITEM:
            item_id = entry.get("id")
            if not isinstance(item_id, str) or not item_id:
                fail("existing pod042 Login item has no ID")
            matches.append(item_id)
    if len(matches) > 1:
        fail("multiple pod042 items exist in the agent vault")
    if matches:
        result = op_command(
            ["item", "get", matches[0], "--vault", VAULT, "--format=json", "--reveal"]
        )
    else:
        result = op_command(["item", "template", "get", "Login"])
    item = json.loads(result.stdout)
    if not isinstance(item, dict):
        fail("1Password Login item must be an object")
    return cast(dict[str, object], item), bool(matches)


def store_password(password: str) -> None:
    item, exists = password_item()
    payload = json.dumps(replace_login_fields(item, password))
    if exists:
        item_id = item.get("id")
        if not isinstance(item_id, str):
            fail("existing pod042 Login item has no ID")
        argv = ["item", "edit", item_id, "--vault", VAULT]
    else:
        argv = ["item", "create", "--vault", VAULT, "-"]
    op_command(argv, input_text=payload)


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
        IdentityError,
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
    ) as error:
        print(f"pod042 first access: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
