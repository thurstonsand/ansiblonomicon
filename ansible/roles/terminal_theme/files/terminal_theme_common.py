from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import cast


class Mode(StrEnum):
    LIGHT = "light"
    DARK = "dark"


VALID_MODES: tuple[Mode, ...] = tuple(Mode)
HOST_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def state_home() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))


def lease_dir() -> Path:
    return state_home() / "terminal-theme" / "leases"


def sync_log_path() -> Path:
    return state_home() / "terminal-theme" / "sync.log"


def positive_int(value: str, *, name: str) -> int:
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def read_mode() -> Mode:
    try:
        value = Path.home().joinpath(".terminal-bg").read_text(encoding="utf-8").strip()
    except OSError:
        return Mode.DARK
    return Mode(value)


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def log_sync(message: str) -> None:
    try:
        log_path = sync_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{int(time.time())} {message}\n")
    except OSError:
        return


def sync_mirror(host: str, mode: Mode) -> None:
    command = f"~/.local/bin/terminal-theme-switch.py --no-mirror-sync {mode}"
    try:
        subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=2",
                "-o",
                "ConnectionAttempts=1",
                "-o",
                "PermitLocalCommand=no",
                host,
                command,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log_sync(f"failed to sync {host}: {exc}")


@dataclass(frozen=True)
class ThemeLease:
    ssh_pid: int
    host: str
    expires_at: int

    @classmethod
    def from_json(cls, text: str) -> ThemeLease:
        data: object = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("lease must be a JSON object")

        lease_data = cast(dict[str, object], data)
        ssh_pid = lease_data.get("ssh_pid")
        host = lease_data.get("host")
        expires_at = lease_data.get("expires_at")
        if not isinstance(ssh_pid, int):
            raise ValueError("lease ssh_pid must be an integer")
        if not isinstance(host, str) or not HOST_RE.fullmatch(host):
            raise ValueError("lease host must be an SSH host alias")
        if not isinstance(expires_at, int):
            raise ValueError("lease expires_at must be an integer")

        lease = cls(ssh_pid=ssh_pid, host=host, expires_at=expires_at)
        lease.validate()
        return lease

    @classmethod
    def from_file(cls, path: Path) -> ThemeLease:
        return cls.from_json(path.read_text(encoding="utf-8"))

    @classmethod
    def add_lease(cls, *, ssh_pid: int, host: str, expires_at: int) -> ThemeLease:
        lease = cls(ssh_pid=ssh_pid, host=host, expires_at=expires_at)
        lease.write()
        return lease

    @classmethod
    def active_leases(cls) -> list[ThemeLease]:
        leases = lease_dir()
        if not leases.exists():
            return []

        now = int(time.time())
        active: list[ThemeLease] = []
        for path in leases.glob("*.json"):
            try:
                lease = cls.from_file(path)
            except OSError, ValueError, json.JSONDecodeError:
                remove_file(path)
                continue
            if lease.is_expired(now):
                remove_file(path)
                continue
            active.append(lease)

        return active

    @classmethod
    def active_hosts(cls) -> set[str]:
        return {lease.host for lease in cls.active_leases()}

    @property
    def path(self) -> Path:
        return lease_dir() / f"{self.ssh_pid}.json"

    def to_json(self) -> str:
        return (
            json.dumps(
                {
                    "ssh_pid": self.ssh_pid,
                    "host": self.host,
                    "expires_at": self.expires_at,
                },
                separators=(",", ":"),
            )
            + "\n"
        )

    def write(self) -> None:
        self.validate()
        write_atomic(self.path, self.to_json())

    def remove(self) -> None:
        remove_file(self.path)

    def is_expired(self, now: int | None = None) -> bool:
        return self.expires_at <= (now if now is not None else int(time.time()))

    def validate(self) -> None:
        if self.ssh_pid <= 0:
            raise ValueError("ssh_pid must be positive")
        if not HOST_RE.fullmatch(self.host):
            raise ValueError(
                "host must contain only letters, numbers, dots, underscores, and dashes"
            )
        if self.expires_at <= 0:
            raise ValueError("expires_at must be positive")


def remove_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
