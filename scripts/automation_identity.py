"""Enroll the existing shared automation identity in native fnox configuration."""

import argparse
from collections.abc import Callable
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import tomllib
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
TOKEN_NAME = "FNOX_HOST_OP_TOKEN"
# SYSTEM and Administrators stand where root does on Unix: they may read the
# identity, but nobody else may. OWNER RIGHTS is the owner, which Python's
# mkdir(mode=0o700) grants on Windows.
WINDOWS_PRIVILEGED_SIDS = {"S-1-5-18", "S-1-5-32-544", "S-1-3-4"}
WINDOWS_ACL_SCRIPT = """
$acl = Get-Acl -LiteralPath $env:IDENTITY_ACL_PATH
$sid = [Security.Principal.SecurityIdentifier]
@{
  owner = $acl.GetOwner($sid).Value
  protected = $acl.AreAccessRulesProtected
  readers = @($acl.GetAccessRules($true, $true, $sid) |
    Where-Object AccessControlType -eq Allow |
    ForEach-Object { $_.IdentityReference.Value })
} | ConvertTo-Json -Compress
"""


class IdentityError(Exception):
    pass


def validate_token(token: str) -> str:
    if not token or any(character.isspace() for character in token):
        raise IdentityError("automation token must be one nonempty value")
    return token


def identity_path(home: Path) -> Path:
    return home / ".config/fnox/config.toml"


if sys.platform == "win32":

    def windows_user_sid() -> str:
        output = subprocess.check_output(
            ["whoami", "/user", "/fo", "csv", "/nh"], text=True
        )
        return output.strip().rsplit(",", 1)[1].strip('"')

    def require_windows_owner_only(path: Path, *, protected: bool) -> None:
        if path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise IdentityError(f"{path} must not be a link")
        acl = cast(
            dict[str, object],
            json.loads(
                subprocess.check_output(
                    [
                        "powershell",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        WINDOWS_ACL_SCRIPT,
                    ],
                    env={**os.environ, "IDENTITY_ACL_PATH": str(path)},
                    text=True,
                )
            ),
        )
        user = windows_user_sid()
        readers = set(cast(list[str], acl["readers"]))
        if (
            acl["owner"] != user
            or (protected and acl["protected"] is not True)
            or not readers <= {user, *WINDOWS_PRIVILEGED_SIDS}
        ):
            raise IdentityError(f"{path} must be readable only by its owner")

    def restrict_to_owner(path: Path) -> None:
        subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"*{windows_user_sid()}:F",
            ],
            check=True,
            capture_output=True,
        )


def read_identity(path: Path, owner: int | None) -> str:
    """Check `owner`'s uid on Unix; Windows passes None and checks its own user."""
    if sys.platform == "win32":
        require_windows_owner_only(path, protected=True)
        with path.open("rb") as source:
            config = tomllib.load(source)
    else:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as source:
            metadata = os.fstat(source.fileno())
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_uid != owner
            ):
                raise IdentityError(
                    "native identity must be an owner-only mode-0600 file"
                )
            config = tomllib.load(source)
    expected = {"secrets": {TOKEN_NAME: {"default": "", "env": False}}}
    secrets = config.get("secrets")
    if not isinstance(secrets, dict):
        raise IdentityError("native identity must contain only its hidden token secret")
    declaration = cast(dict[str, object], secrets).get(TOKEN_NAME)
    if not isinstance(declaration, dict):
        raise IdentityError("native identity must contain its hidden token secret")
    token = cast(dict[str, object], declaration).get("default")
    if not isinstance(token, str):
        raise IdentityError("native identity token must be a string")
    expected["secrets"][TOKEN_NAME]["default"] = token
    if (
        config != expected
        or cast(dict[str, object], declaration).get("env") is not False
    ):
        raise IdentityError("native identity must contain only its hidden token secret")
    return validate_token(token)


def clean_environment(
    inherited: dict[str, str], secret_keys: set[str]
) -> dict[str, str]:
    return {
        key: value
        for key, value in inherited.items()
        if key not in secret_keys
        and not key.startswith("FNOX_")
        and key
        not in {
            "OP_SERVICE_ACCOUNT_TOKEN",
            "OP_CONNECT_HOST",
            "OP_CONNECT_TOKEN",
            "OP_ACCOUNT",
        }
    }


def file_revision(path: Path) -> tuple[int, ...] | None:
    if not (path.exists() or path.is_symlink()):
        return None
    metadata = path.lstat()
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_gid,
    )


def current_identity_revision(destination: Path) -> tuple[int, ...] | None:
    if not (destination.exists() or destination.is_symlink()):
        return None
    read_identity(destination, None if sys.platform == "win32" else os.getuid())
    return file_revision(destination)


def install_identity(
    destination: Path,
    token: str,
    previous: tuple[int, ...] | None,
    verify: Callable[[Path], None] | None = None,
) -> None:
    token = validate_token(token)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if sys.platform == "win32":
        require_windows_owner_only(destination.parent, protected=False)
    else:
        directory_metadata = destination.parent.lstat()
        if (
            not stat.S_ISDIR(directory_metadata.st_mode)
            or directory_metadata.st_uid != os.getuid()
            or directory_metadata.st_mode & 0o022
        ):
            raise IdentityError(
                "native identity directory must be owned and not writable by others"
            )
    with tempfile.TemporaryDirectory(
        prefix=".enroll-", dir=destination.parent
    ) as temporary:
        candidate = Path(temporary) / "config.toml"
        content = (
            f"[secrets.{TOKEN_NAME}]\ndefault = {json.dumps(token)}\nenv = false\n"
        )
        if sys.platform == "win32":
            candidate.touch(exist_ok=False)
            restrict_to_owner(candidate)
            descriptor = os.open(candidate, os.O_WRONLY)
        else:
            descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if verify is not None:
            verify(candidate)
        if file_revision(destination) != previous:
            raise IdentityError("native identity changed during enrollment")
        os.replace(candidate, destination)
        if sys.platform != "win32":
            descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)


def enroll(
    destination: Path,
    root: Path,
    fnox: str,
    inherited: dict[str, str],
    profile: str = "macos",
) -> None:
    previous = current_identity_revision(destination)
    environment = clean_environment(
        inherited, {"POD042_SERVICE_ACCOUNT_TOKEN", "NEXTDNS_PROFILE_ID"}
    )
    environment["FNOX_CONFIG_DIR"] = os.devnull
    result = subprocess.run(
        [
            fnox,
            "--config",
            str(root / f"fnox.{profile}.toml"),
            "--profile",
            profile,
            "--no-daemon",
            "--if-missing",
            "error",
            "get",
            "POD042_SERVICE_ACCOUNT_TOKEN",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise IdentityError(
            "desktop authentication could not read the automation identity"
        )
    token = validate_token(result.stdout.strip())

    def verify(candidate: Path) -> None:
        environment["FNOX_CONFIG_DIR"] = str(candidate.parent)
        probe = subprocess.run(
            [
                fnox,
                "--config",
                str(root / "fnox.toml"),
                "--no-daemon",
                "--non-interactive",
                "--if-missing",
                "error",
                "get",
                "NEXTDNS_PROFILE_ID",
            ],
            env=environment,
            capture_output=True,
            check=False,
        )
        if probe.returncode or not probe.stdout.strip():
            raise IdentityError("candidate automation identity failed its fnox probe")

    install_identity(destination, token, previous, verify)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--orb", action="store_true", help="Install the identity supplied by Amp"
    )
    arguments = parser.parse_args()
    destination = identity_path(Path.home())
    if arguments.orb:
        token = os.environ.get("OP_SERVICE_ACCOUNT_TOKEN")
        if token is None:
            raise IdentityError("Orb automation identity was not supplied")
        previous = current_identity_revision(destination)
        install_identity(destination, token, previous)
        print("Orb automation identity installed; no provider token exported.")
        return
    fnox = subprocess.check_output(
        ["mise", "--no-env", "-C", str(ROOT), "which", "fnox"], text=True
    ).strip()
    profile = {"type-a-no2": "omarchy", "eve": "windows"}.get(
        socket.gethostname().split(".", 1)[0], "macos"
    )
    enroll(destination, ROOT, fnox, dict(os.environ), profile)
    print("Automation identity enrolled; no provider token exported.")


if __name__ == "__main__":
    try:
        main()
    except (
        IdentityError,
        OSError,
        tomllib.TOMLDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        raise SystemExit(f"automation-identity: {error}") from None
