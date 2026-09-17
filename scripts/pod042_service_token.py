#!/usr/bin/env python3
"""Install and verify pod042's retained 1Password service token."""

import argparse
from collections.abc import Sequence
import fcntl
import os
from pathlib import Path
import pwd
import secrets
import shlex
import socket
import stat
import subprocess
import sys

import fnox_host
import pod042_reconcile as reconcile

USER = "thurstonsand"
PROBE_KEY = "HARK_WEBHOOK_URL_POD042"
REMOTE_CHECKOUT = "/home/thurstonsand/code/ansiblonomicon"
REMOTE_SCRIPT = f"{REMOTE_CHECKOUT}/scripts/pod042_service_token.py"
DEFAULT_REMOTE = "pod042"
OPERATOR_PUBLIC_KEY = reconcile.TARGET_ROOT / "base" / "files" / "operator.pub"
IDENTITY_AGENT_ENV = "POD042_SSH_IDENTITY_AGENT"
CONTROL_PATH_ENV = "POD042_SSH_CONTROL_PATH"
MAX_TOKEN_BYTES = 65536


class ServiceTokenError(Exception):
    pass


# Delivering this token is the one operation left that reaches pod042 from the
# workstation, so the SSH and checkout-matching helpers live here rather than in
# the reconcile module, which now only ever runs on the machine itself.
def ssh_options() -> list[str]:
    options = ["-i", str(OPERATOR_PUBLIC_KEY), "-o", "IdentitiesOnly=yes"]
    if identity_agent := os.environ.get(IDENTITY_AGENT_ENV):
        options.extend(["-o", f"IdentityAgent={identity_agent}"])
    if control_path := os.environ.get(CONTROL_PATH_ENV):
        options.extend(["-o", f"ControlPath={control_path}"])
    return options


def assert_remote_hostname(host: str) -> None:
    actual = reconcile.command_output(ssh_command(host, ["hostname", "-s"]))
    if actual != reconcile.EXPECTED_HOSTNAME:
        raise ServiceTokenError(
            f"pod042 target requires hostname {reconcile.EXPECTED_HOSTNAME!r}, "
            f"got {actual!r}"
        )


def git_output(repo: Path, *args: str) -> str:
    return reconcile.command_output(["git", "-C", str(repo), *args])


def local_deploy_revision(repo: Path) -> tuple[str, str]:
    if git_output(repo, "status", "--porcelain"):
        raise ServiceTokenError("workstation checkout has local changes")
    branch = git_output(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    if not branch:
        raise ServiceTokenError("workstation checkout has a detached HEAD")
    try:
        upstream = git_output(
            repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
        )
    except subprocess.CalledProcessError as error:
        raise ServiceTokenError(
            f"workstation branch {branch!r} has no upstream"
        ) from error
    revision = git_output(repo, "rev-parse", "HEAD")
    if revision != git_output(repo, "rev-parse", upstream):
        raise ServiceTokenError(
            f"workstation branch {branch!r} is not exactly at {upstream}"
        )
    return branch, revision


def remote_git(host: str, *args: str) -> str:
    return reconcile.command_output(
        ssh_command(host, ["git", "-C", REMOTE_CHECKOUT, *args])
    )


def remote_checkout_exists(host: str) -> bool:
    result = subprocess.run(
        ssh_command(host, ["test", "-d", f"{REMOTE_CHECKOUT}/.git"]),
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def validate_remote_checkout(host: str, branch: str) -> str:
    if remote_git(host, "status", "--porcelain"):
        raise ServiceTokenError("pod042 checkout has local changes")
    remote_branch = remote_git(host, "symbolic-ref", "--quiet", "--short", "HEAD")
    if remote_branch != branch:
        raise ServiceTokenError(
            f"pod042 checkout branch {remote_branch!r} does not match "
            f"workstation branch {branch!r}"
        )
    return remote_git(host, "rev-parse", "HEAD")


def token_record(value: str) -> str:
    token = value.strip()
    if (
        not token
        or "\n" in token
        or "\r" in token
        or len(value.encode()) > MAX_TOKEN_BYTES
    ):
        raise ServiceTokenError("expected one nonempty service-token record")
    return token


def read_token_input() -> str:
    return token_record(sys.stdin.read(MAX_TOKEN_BYTES + 1))


def ssh_command(host: str, arguments: Sequence[str]) -> list[str]:
    return [
        "ssh",
        "-T",
        "-o",
        "BatchMode=yes",
        *ssh_options(),
        host,
        shlex.join(arguments),
    ]


def secret_command(arguments: Sequence[str], *, token: str, label: str) -> None:
    result = subprocess.run(arguments, input=token + "\n", text=True, check=False)
    if result.returncode:
        raise ServiceTokenError(f"{label} failed")


def probe_token(token: str) -> None:
    inherited = dict(os.environ)
    inherited["PATH"] = "/usr/local/bin:/usr/bin:/bin"
    invocation = fnox_host.prepare_invocation(
        reconcile.ROOT,
        "pod042",
        "get",
        [PROBE_KEY],
        inherited,
        token,
        fnox="/usr/local/bin/fnox",
    )
    result = subprocess.run(
        invocation.argv,
        env=invocation.environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode or not result.stdout.strip():
        raise ServiceTokenError("1Password token probe failed")


def child_directory(
    parent: int, name: str, uid: int, gid: int, *, private: bool
) -> tuple[int, bool]:
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent)
        changed = True
    except FileExistsError:
        changed = False
    descriptor = os.open(
        name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
    )
    try:
        metadata = os.fstat(descriptor)
        if metadata.st_uid not in {0, uid}:
            raise ServiceTokenError(f"{name}: directory belongs to another account")
        if (metadata.st_uid, metadata.st_gid) != (uid, gid):
            os.fchown(descriptor, uid, gid)
            changed = True
        if private and stat.S_IMODE(metadata.st_mode) != 0o700:
            os.fchmod(descriptor, 0o700)
            changed = True
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor, changed


def converge_token(home: Path, token: str, uid: int, gid: int) -> bool:
    token = token_record(token)
    home_fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.fstat(home_fd).st_uid != uid:
            raise ServiceTokenError("operator home belongs to another account")
        config_fd, config_changed = child_directory(
            home_fd, ".config", uid, gid, private=False
        )
        try:
            token_dir, directory_changed = child_directory(
                config_fd, "op-service-account", uid, gid, private=True
            )
        finally:
            os.close(config_fd)
    finally:
        os.close(home_fd)
    temporary = ".token-" + secrets.token_hex(12)
    created = False
    try:
        fcntl.flock(token_dir, fcntl.LOCK_EX)
        removed_stale = False
        for name in os.listdir(token_dir):
            if name.startswith(".token-"):
                os.unlink(name, dir_fd=token_dir)
                removed_stale = True
        if removed_stale:
            os.fsync(token_dir)
        try:
            current_fd = os.open(
                "token", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=token_dir
            )
        except FileNotFoundError:
            current_fd = None
        if current_fd is not None:
            metadata = os.fstat(current_fd)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != uid
                or metadata.st_nlink != 1
            ):
                os.close(current_fd)
                raise ServiceTokenError(
                    "existing token must be an operator-owned regular file without hard links"
                )
            with os.fdopen(current_fd, "rb") as source:
                current = source.read(MAX_TOKEN_BYTES + 1)
                if (
                    current == (token + "\n").encode()
                    and stat.S_IMODE(metadata.st_mode) == 0o600
                    and metadata.st_gid == gid
                ):
                    return config_changed or directory_changed or removed_stale
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=token_dir,
        )
        created = True
        with os.fdopen(descriptor, "w") as destination:
            os.fchown(destination.fileno(), uid, gid)
            destination.write(token + "\n")
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, "token", src_dir_fd=token_dir, dst_dir_fd=token_dir)
        created = False
        os.fsync(token_dir)
        return True
    finally:
        if created:
            os.unlink(temporary, dir_fd=token_dir)
        os.close(token_dir)


def receive_token(token: str) -> None:
    reconcile.assert_hostname()
    if os.geteuid() != 0:
        raise ServiceTokenError("service-token installation requires root")
    operator = pwd.getpwnam(USER)
    if (
        Path(operator.pw_dir) / ".config/op-service-account/token"
        != fnox_host.TOKEN_PATH
    ):
        raise ServiceTokenError("operator home does not match the declared token path")
    probe_token(token)
    probe_command = [
        "sudo",
        "-n",
        "-u",
        USER,
        "--",
        "/usr/bin/python3",
        "-B",
        str(Path(__file__).resolve()),
    ]
    secret_command(
        [*probe_command, "--probe"],
        token=token,
        label="operator token probe",
    )
    changed = converge_token(
        Path(operator.pw_dir), token, operator.pw_uid, operator.pw_gid
    )
    installed = fnox_host.read_token(fnox_host.TOKEN_PATH, operator.pw_uid)
    if installed != token:
        raise ServiceTokenError("installed token did not match the validated candidate")
    secret_command(
        [*probe_command, "--probe-installed"],
        token=token,
        label="installed operator token probe",
    )
    print(
        "pod042: service token "
        + ("updated" if changed else "unchanged")
        + "; root/operator probes passed"
    )


def install_remote_token(host: str) -> None:
    profile = fnox_host.select_profile(socket.gethostname(), orb=False)
    if profile != "macos":
        raise ServiceTokenError(
            "service-token installation requires the macos workstation"
        )
    branch, revision = local_deploy_revision(reconcile.ROOT)
    assert_remote_hostname(host)
    if not remote_checkout_exists(host):
        raise ServiceTokenError(
            "pod042 checkout is missing; clone it on the machine first"
        )
    if validate_remote_checkout(host, branch) != revision:
        raise ServiceTokenError(
            "pod042 must match the workstation revision; reconcile it first"
        )
    reconcile.run_command(ssh_command(host, ["sudo", "-n", "true"]))
    binary = reconcile.command_output(["mise", "--no-env", "which", "fnox"])
    invocation = fnox_host.prepare_invocation(
        reconcile.ROOT,
        profile,
        "get",
        ["POD042_SERVICE_ACCOUNT_TOKEN"],
        dict(os.environ),
        None,
        fnox=binary,
    )
    result = subprocess.run(
        invocation.argv,
        env=invocation.environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ServiceTokenError(
            "could not resolve POD042_SERVICE_ACCOUNT_TOKEN; check 1Password desktop authorization"
        )
    token = token_record(result.stdout)
    secret_command(
        ssh_command(
            host,
            ["sudo", "-n", "--", "/usr/bin/python3", "-B", REMOTE_SCRIPT, "--receive"],
        ),
        token=token,
        label="remote service-token installation",
    )


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_REMOTE)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--receive", action="store_true", help=argparse.SUPPRESS)
    mode.add_argument("--probe", action="store_true", help=argparse.SUPPRESS)
    mode.add_argument("--probe-installed", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if arguments.receive:
        receive_token(read_token_input())
    elif arguments.probe_installed:
        reconcile.assert_hostname()
        expected = read_token_input()
        token = fnox_host.read_token(fnox_host.TOKEN_PATH, pwd.getpwnam(USER).pw_uid)
        if token != expected:
            raise ServiceTokenError(
                "installed operator token did not match the candidate"
            )
        probe_token(token)
    elif arguments.probe:
        reconcile.assert_hostname()
        probe_token(read_token_input())
    else:
        install_remote_token(arguments.host)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (
        ServiceTokenError,
        fnox_host.ConfigurationError,
        reconcile.ReconcileError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"pod042: {error}", file=sys.stderr)
        raise SystemExit(1) from None
