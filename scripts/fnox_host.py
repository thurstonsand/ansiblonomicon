"""Select a declared host identity and delegate secret resolution to fnox."""

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import pwd
import shlex
import socket
import stat
import subprocess
import sys
import tomllib
from typing import cast

from automation_identity import (
    IdentityError,
    clean_environment,
    identity_path,
    read_identity,
)

ROOT = Path(__file__).resolve().parents[1]
HOST_PROFILES = {
    "Thurstons-MacBook-Pro": "macos",
    "ML-DFC6YK6VJQ": "work",
    "pod042": "pod042",
}
PROFILES = ("macos", "work", "pod042", "orb")
EXEC_PROFILE = "ANSIBLONOMICON_EXEC_PROFILE"
TOKEN_NAME = "FNOX_HOST_OP_TOKEN"
TOKEN_PATH = Path("/home/thurstonsand/.config/op-service-account/token")


class ConfigurationError(Exception):
    pass


def select_profile(hostname: str, *, orb: bool) -> str:
    if orb:
        return "orb"
    short_hostname = hostname.split(".", 1)[0]
    if short_hostname not in HOST_PROFILES:
        raise ConfigurationError(
            f"unregistered host {short_hostname!r}; expected "
            + ", ".join(HOST_PROFILES)
        )
    return HOST_PROFILES[short_hostname]


def table(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{label} must be a table")
    return cast(dict[str, object], value)


def load_declaration(path: Path, *, host: bool) -> set[str]:
    with path.open("rb") as source:
        config = tomllib.load(source)
    allowed = {
        "root",
        "env",
        "if_missing",
        "prompt_auth",
        "daemon",
        "providers",
        "secrets",
    }
    if host:
        allowed.add("import")
    if extra := config.keys() - allowed:
        raise ConfigurationError(f"{path.name}: unsupported settings: {sorted(extra)}")
    if host and config.get("import") != ["fnox.toml"]:
        raise ConfigurationError(f"{path.name}: must import only fnox.toml")
    required = {"env": "exec", "if_missing": "error", "prompt_auth": False}
    for key, value in required.items():
        if (not host or key in config) and config.get(key) != value:
            raise ConfigurationError(f"{path.name}: {key} must be {value!r}")
    if (not host or "daemon" in config) and config.get("daemon") != {"enabled": False}:
        raise ConfigurationError(f"{path.name}: daemon must be disabled")
    if not host and config.get("root") is not True:
        raise ConfigurationError(f"{path.name}: root must be true")
    secrets = table(config.get("secrets", {}), f"{path.name}: secrets")
    for name, raw_declaration in secrets.items():
        declaration = table(raw_declaration, f"{path.name}: {name}")
        if declaration.keys() - {"provider", "value", "env", "description"}:
            raise ConfigurationError(f"{path.name}: {name} has unsupported settings")
        if not declaration.get("provider") or not declaration.get("value"):
            raise ConfigurationError(f"{path.name}: {name} needs provider and value")
        export = declaration.get("env", "exec")
        if export != "exec" and export is not False and export is not True:
            raise ConfigurationError(f"{path.name}: {name} has invalid export policy")
    return set(secrets)


def declared_keys(root: Path) -> set[str]:
    keys = load_declaration(root / "fnox.toml", host=False)
    for profile in PROFILES:
        keys.update(load_declaration(root / f"fnox.{profile}.toml", host=True))
    return keys


def read_token(path: Path, owner: int) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "r") as source:
        metadata = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != owner
        ):
            raise ConfigurationError(
                "service token must be an operator-owned mode-0600 regular file"
            )
        token = source.read().strip()
    if not token or "\n" in token or "\r" in token:
        raise ConfigurationError("service token must be one nonempty line")
    return token


def authentication_environment(
    profile: str,
    inherited: dict[str, str],
    secret_keys: set[str],
    token: str | None,
    *,
    native_identity: bool = False,
) -> dict[str, str]:
    environment = clean_environment(inherited, secret_keys)
    if profile in {"pod042", "orb"}:
        if not native_identity and (
            not token or not token.strip() or "\n" in token or "\r" in token
        ):
            raise ConfigurationError(f"{profile} requires a nonempty service token")
        environment = {
            key: value
            for key, value in environment.items()
            if not key.startswith("OP_SESSION_")
        }
        if token is not None:
            environment[TOKEN_NAME] = token
    if profile == "work" and (account := inherited.get("FNOX_WORK_ACCOUNT")):
        environment["FNOX_WORK_ACCOUNT"] = account
    return environment


def child_command(
    command: list[str], environment: dict[str, str], *, profile: str | None = None
) -> list[str]:
    if "=" in command[0]:
        raise ConfigurationError(
            "exec requires an executable, not an environment assignment"
        )
    scrub = sorted(key for key in environment if key.startswith(("OP_", "FNOX_")))
    args = ["/usr/bin/env"]
    for key in scrub:
        args.extend(["-u", key])
    args.append("--")
    if profile is not None:
        args.append(f"{EXEC_PROFILE}={profile}")
    args.extend(command)
    return args


@dataclass
class FnoxCommand:
    argv: list[str]
    environment: dict[str, str]


def build_command(
    root: Path,
    profile: str,
    operation: str,
    arguments: list[str],
    inherited: dict[str, str],
    token: str | None,
    *,
    fnox: str = "fnox",
) -> FnoxCommand:
    if profile not in PROFILES:
        raise ConfigurationError(f"unsupported profile: {profile}")
    if operation not in {"get", "exec", "export"} or (
        operation != "export" and not arguments
    ):
        raise ConfigurationError("expected get NAME, exec COMMAND, or export")
    if operation == "export" and arguments:
        raise ConfigurationError("export does not accept arguments")
    keys = declared_keys(root)
    if not inherited.get("HOME"):
        raise ConfigurationError("HOME is required for the native host identity")
    home = Path(inherited["HOME"])
    identity = identity_path(home)
    native = identity.exists() or identity.is_symlink()
    if native:
        configured_token = read_identity(identity, home.stat().st_uid)
        if token is not None and token != configured_token:
            raise ConfigurationError("native and injected automation identities differ")
    environment = authentication_environment(
        profile, inherited, keys, token, native_identity=native
    )
    environment["FNOX_CONFIG_DIR"] = str(identity.parent)
    command = [
        fnox,
        "--config",
        str(root.resolve() / f"fnox.{profile}.toml"),
        "--profile",
        profile,
        "--no-daemon",
        "--non-interactive",
        "--if-missing",
        "error",
    ]
    if operation == "get":
        command.extend(["get", *arguments])
    elif operation == "export":
        command.extend(["export", "--format", "shell"])
    else:
        command.extend(
            ["exec", "--", *child_command(arguments, environment, profile=profile)]
        )
    return FnoxCommand(command, environment)


def inherited_execution(profile: str, operation: str, command: list[str]) -> int:
    declarations: dict[str, dict[str, object]] = {}
    for path in (ROOT / "fnox.toml", ROOT / f"fnox.{profile}.toml"):
        with path.open("rb") as source:
            config = tomllib.load(source)
        declarations.update(config["secrets"])
    expected = {
        key
        for key, declaration in declarations.items()
        if declaration.get("env") is not False
    }
    actual = declared_keys(ROOT) & os.environ.keys()
    if actual != expected or any(not os.environ[key] for key in expected):
        raise ConfigurationError(
            "incomplete scoped secret environment; start a fresh authenticated launch"
        )
    if operation == "get":
        if command[0] not in expected:
            raise ConfigurationError(
                "requested secret is not available in this process context"
            )
        print(os.environ[command[0]])
        return 0
    if operation == "export":
        for key, declaration in declarations.items():
            if declaration.get("env") is True:
                print(f"export {shlex.quote(key)}={shlex.quote(os.environ[key])}")
        return 0
    invocation = child_command(command, dict(os.environ), profile=profile)
    os.execv(invocation[0], invocation)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--orb", action="store_true", help="Use the supplied Orb service identity"
    )
    commands = parser.add_subparsers(dest="operation", required=True)
    commands.add_parser("profile")
    commands.add_parser("export")
    get = commands.add_parser("get")
    get.add_argument("name")
    execute = commands.add_parser("exec")
    execute.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    context = os.environ.get(EXEC_PROFILE)
    profile = select_profile(
        socket.gethostname(), orb=arguments.orb or context == "orb"
    )
    if context is not None and context != profile:
        raise ConfigurationError("scoped secret profile does not match this launch")
    if arguments.operation == "profile":
        print(profile)
        return 0
    command: list[str] = []
    if arguments.operation == "get":
        command = [arguments.name]
    elif arguments.operation == "exec":
        command = arguments.command
    if command and command[0] == "--":
        command = command[1:]
    if not command and arguments.operation != "export":
        parser.error("exec requires a command after --")
    if context is not None:
        return inherited_execution(profile, arguments.operation, command)
    token = None
    identity = identity_path(Path.home())
    if not (identity.exists() or identity.is_symlink()):
        if profile == "pod042":
            token = read_token(TOKEN_PATH, pwd.getpwnam("thurstonsand").pw_uid)
        elif profile == "orb":
            token = os.environ.get("OP_SERVICE_ACCOUNT_TOKEN")
    binary = "fnox"
    if profile == "pod042":
        binary = "/usr/local/bin/fnox"
    elif profile in {"macos", "work"}:
        binary = subprocess.check_output(
            ["mise", "--no-env", "-C", str(ROOT), "which", "fnox"], text=True
        ).strip()
    invocation = build_command(
        ROOT,
        profile,
        arguments.operation,
        command,
        dict(os.environ),
        token,
        fnox=binary,
    )
    os.execvpe(invocation.argv[0], invocation.argv, invocation.environment)


def entrypoint() -> None:
    try:
        code = main()
    except (
        ConfigurationError,
        IdentityError,
        OSError,
        tomllib.TOMLDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"fnox-host: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    raise SystemExit(code)


if __name__ == "__main__":
    entrypoint()
