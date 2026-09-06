"""Enroll the existing shared automation identity in native fnox configuration."""

import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import tomllib
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
TOKEN_NAME = "FNOX_HOST_OP_TOKEN"


class IdentityError(Exception):
    pass


def validate_token(token: str) -> str:
    if not token or any(character.isspace() for character in token):
        raise IdentityError("automation token must be one nonempty value")
    return token


def identity_path(home: Path) -> Path:
    return home / ".config/fnox/config.toml"


def read_identity(path: Path, owner: int) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        metadata = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != owner
        ):
            raise IdentityError("native identity must be an owner-only mode-0600 file")
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


def enroll(
    destination: Path,
    root: Path,
    fnox: str,
    inherited: dict[str, str],
) -> None:
    previous = None
    if destination.exists() or destination.is_symlink():
        read_identity(destination, os.getuid())
        previous = file_revision(destination)
    environment = clean_environment(
        inherited, {"POD042_SERVICE_ACCOUNT_TOKEN", "NEXTDNS_PROFILE_ID"}
    )
    environment["FNOX_CONFIG_DIR"] = "/dev/null"
    result = subprocess.run(
        [
            fnox,
            "--config",
            str(root / "fnox.macos.toml"),
            "--profile",
            "macos",
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
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
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
        directory = Path(temporary)
        candidate = directory / "config.toml"
        content = (
            f"[secrets.{TOKEN_NAME}]\ndefault = {json.dumps(token)}\nenv = false\n"
        )
        descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        environment["FNOX_CONFIG_DIR"] = str(directory)
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
        if file_revision(destination) != previous:
            raise IdentityError("native identity changed during enrollment")
        os.replace(candidate, destination)
        descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def main() -> None:
    fnox = subprocess.check_output(
        ["mise", "--no-env", "-C", str(ROOT), "which", "fnox"], text=True
    ).strip()
    enroll(identity_path(Path.home()), ROOT, fnox, dict(os.environ))
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
