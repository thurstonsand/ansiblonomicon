#!/usr/bin/env python3
"""Reconcile pod042 through its shared native mise bootstrap target."""

import argparse
from collections.abc import Sequence
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
from typing import NoReturn

ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP_ROOT = ROOT / "bootstrap"
TARGET_ROOT = BOOTSTRAP_ROOT / "targets" / "pod042"
REMOTE_CHECKOUT = "/home/thurstonsand/code/ansiblonomicon"
DEFAULT_REMOTE = "pod042"
EXPECTED_HOSTNAME = "pod042"
REMOTE_USER = "thurstonsand"
OPERATOR_PUBLIC_KEY = TARGET_ROOT / "base" / "files" / "operator.pub"
IDENTITY_AGENT_ENV = "POD042_SSH_IDENTITY_AGENT"
CAPABILITIES = ("base", "storage")


class ReconcileError(Exception):
    pass


def run_command(
    argv: Sequence[str],
    *,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=check,
        capture_output=capture_output,
        text=True,
    )


def command_output(argv: Sequence[str]) -> str:
    return run_command(argv, capture_output=True).stdout.strip()


def ssh_options() -> list[str]:
    options = [
        "-i",
        str(OPERATOR_PUBLIC_KEY),
        "-o",
        "IdentitiesOnly=yes",
    ]
    if identity_agent := os.environ.get(IDENTITY_AGENT_ENV):
        options.extend(["-o", f"IdentityAgent={identity_agent}"])
    return options


def ssh_command(host: str, argv: Sequence[str]) -> list[str]:
    return ["ssh", *ssh_options(), host, shlex.join(argv)]


def remote_output(host: str, argv: Sequence[str]) -> str:
    return command_output(ssh_command(host, argv))


def fail(message: str) -> NoReturn:
    raise ReconcileError(message)


def assert_hostname(host: str | None) -> None:
    if host is None:
        actual = socket.gethostname().split(".", maxsplit=1)[0]
    else:
        actual = remote_output(host, ["hostname", "-s"])
    if actual != EXPECTED_HOSTNAME:
        fail(f"pod042 target requires hostname {EXPECTED_HOSTNAME!r}, got {actual!r}")


def git_output(repo: Path, *args: str) -> str:
    return command_output(["git", "-C", str(repo), *args])


def require_clean_checkout(repo: Path, label: str) -> None:
    if git_output(repo, "status", "--porcelain"):
        fail(f"{label} checkout has local changes")


def local_deploy_revision(repo: Path) -> tuple[str, str]:
    require_clean_checkout(repo, "workstation")
    branch = git_output(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    if not branch:
        fail("workstation checkout has a detached HEAD")
    try:
        upstream = git_output(
            repo,
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
        )
    except subprocess.CalledProcessError:
        fail(f"workstation branch {branch!r} has no upstream")
    revision = git_output(repo, "rev-parse", "HEAD")
    upstream_revision = git_output(repo, "rev-parse", upstream)
    if revision != upstream_revision:
        fail(f"workstation branch {branch!r} is not exactly at {upstream}")
    return branch, revision


def remote_git(
    host: str, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return run_command(
        ssh_command(host, ["git", "-C", REMOTE_CHECKOUT, *args]),
        check=check,
        capture_output=True,
    )


def remote_checkout_exists(host: str) -> bool:
    result = run_command(
        ssh_command(host, ["test", "-d", f"{REMOTE_CHECKOUT}/.git"]),
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def validate_remote_checkout(host: str, branch: str) -> str:
    if remote_git(host, "status", "--porcelain").stdout.strip():
        fail("pod042 checkout has local changes")
    remote_branch = remote_git(
        host, "symbolic-ref", "--quiet", "--short", "HEAD"
    ).stdout.strip()
    if remote_branch != branch:
        fail(
            f"pod042 checkout branch {remote_branch!r} does not match "
            f"workstation branch {branch!r}"
        )
    return remote_git(host, "rev-parse", "HEAD").stdout.strip()


def fast_forward_remote_checkout(host: str, branch: str, revision: str) -> None:
    current = validate_remote_checkout(host, branch)
    if current == revision:
        return
    remote_git(host, "fetch", "origin", branch)
    fetched = remote_git(host, "rev-parse", f"origin/{branch}").stdout.strip()
    if fetched != revision:
        fail(f"origin/{branch} on pod042 is {fetched}, expected workstation {revision}")
    ancestor = remote_git(
        host, "merge-base", "--is-ancestor", current, revision, check=False
    )
    if ancestor.returncode != 0:
        fail("pod042 checkout cannot fast-forward to the workstation revision")
    remote_git(host, "merge", "--ff-only", revision)


def capabilities_for(capability: str | None) -> tuple[str, ...]:
    if capability is None:
        return CAPABILITIES
    if capability not in CAPABILITIES:
        fail(f"unknown pod042 capability: {capability}")
    return (capability,)


def isolated_mise_command(ceiling: Path, directory: Path) -> list[str]:
    return [
        "env",
        f"MISE_CEILING_PATHS={ceiling}",
        "mise",
        "-C",
        str(directory),
    ]


def run_local(capability: str | None, check_mode: bool) -> None:
    assert_hostname(None)
    environments = ",".join(capabilities_for(capability))
    command = [
        "env",
        f"MISE_CEILING_PATHS={TARGET_ROOT.parent}",
        f"MISE_ENV={environments}",
        "mise",
        "-C",
        str(TARGET_ROOT),
    ]
    if check_mode:
        run_command([*command, "bootstrap", "plan"])
    else:
        run_command([*command, "bootstrap", "--yes"])


def remote_bootstrap_command(
    host: str,
    capability: str | None,
    check_mode: bool,
    install_mise: bool,
) -> list[str]:
    environments = ",".join(capabilities_for(capability))
    command = [
        *isolated_mise_command(ROOT, BOOTSTRAP_ROOT),
        "bootstrap",
        "remote",
        "--host",
        f"{REMOTE_USER}@{host}",
        "--source",
        str(TARGET_ROOT.relative_to(BOOTSTRAP_ROOT)),
        "--remote-env",
        environments,
        "--ssh-option",
        f"IdentityFile={OPERATOR_PUBLIC_KEY}",
        "--ssh-option",
        "IdentitiesOnly=yes",
    ]
    if identity_agent := os.environ.get(IDENTITY_AGENT_ENV):
        command.extend(["--ssh-option", f"IdentityAgent={identity_agent}"])
    command.append("--yes")
    if not install_mise:
        command.extend(["--remote-mise", "/usr/local/bin/mise"])
    if check_mode:
        command.append("--dry-run")
    return command


def run_remote(
    host: str,
    capability: str | None,
    check_mode: bool,
    install_mise: bool,
    initial: bool,
) -> None:
    assert_hostname(host)
    branch, revision = local_deploy_revision(ROOT)
    if remote_checkout_exists(host):
        validate_remote_checkout(host, branch)
        if not check_mode:
            fast_forward_remote_checkout(host, branch, revision)
    elif not initial:
        fail("pod042 checkout is missing; use the first-access bootstrap")
    elif branch != "main":
        fail("first bootstrap requires the workstation checkout on main")
    run_command(
        remote_bootstrap_command(
            host,
            capability,
            check_mode,
            install_mise or initial,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capability", nargs="?")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--update-mise", action="store_true")
    parser.add_argument("--host", default=DEFAULT_REMOTE)
    parser.add_argument("--initial", action="store_true", help=argparse.SUPPRESS)
    return parser


def run(argv: Sequence[str]) -> int:
    args = build_parser().parse_args(argv)
    if args.check and args.update_mise:
        fail("--check and --update-mise cannot be combined")
    local = socket.gethostname().split(".", maxsplit=1)[0] == EXPECTED_HOSTNAME
    if local:
        if args.initial or args.host != DEFAULT_REMOTE:
            fail("--initial and --host are only valid from a workstation")
        if args.update_mise:
            fail("run system-wide mise updates from a workstation")
        run_local(args.capability, args.check)
    else:
        run_remote(
            args.host,
            args.capability,
            args.check,
            args.update_mise,
            args.initial,
        )
    return 0


def main() -> int:
    try:
        return run(sys.argv[1:])
    except (ReconcileError, subprocess.CalledProcessError) as error:
        print(f"pod042: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
