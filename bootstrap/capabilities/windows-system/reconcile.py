#!/usr/bin/env python3
"""Reconcile the declared Windows time zone and registry values, elevating once for machine keys."""

import argparse
import ctypes
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
import tomllib
from typing import cast
import winreg

if sys.platform != "win32":
    raise SystemExit("windows-system runs only on Windows")

HIVES = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
TYPES = {int: winreg.REG_DWORD, str: winreg.REG_SZ}
ELEVATE = """
$process = Start-Process -FilePath $env:WINDOWS_SYSTEM_PYTHON `
  -ArgumentList $env:WINDOWS_SYSTEM_ARGUMENTS -Verb RunAs -WindowStyle Hidden `
  -Wait -PassThru
exit $process.ExitCode
"""


@dataclass(frozen=True)
class Value:
    hive: str
    key: str
    name: str
    data: int | str

    def __str__(self) -> str:
        return f"{self.hive}\\{self.key}\\{self.name}"


def declarations(path: Path) -> tuple[str, list[Value]]:
    with path.open("rb") as source:
        declared = tomllib.load(source)
    timezone = cast(str, declared["timezone"])
    registry = cast(dict[str, dict[str, object]], declared["registry"])
    values: list[Value] = []
    for location, entries in registry.items():
        hive, key = location.split("\\", 1)
        if hive not in HIVES:
            raise ValueError(f"{location}: hive must be one of {', '.join(HIVES)}")
        for name, data in entries.items():
            if type(data) not in TYPES:
                raise ValueError(f"{location}\\{name}: expected an integer or string")
            values.append(Value(hive, key, name, cast(int | str, data)))
    return timezone, values


def current_timezone() -> str:
    return subprocess.run(
        ["tzutil", "/g"], capture_output=True, text=True, check=True
    ).stdout.strip()


def current(value: Value) -> tuple[object, int] | None:
    try:
        with winreg.OpenKey(HIVES[value.hive], value.key) as key:
            return cast(tuple[object, int], winreg.QueryValueEx(key, value.name))
    except FileNotFoundError:
        return None


def drifted(values: list[Value]) -> list[Value]:
    return [
        value
        for value in values
        if current(value) != (value.data, TYPES[type(value.data)])
    ]


def write(value: Value) -> None:
    with winreg.CreateKeyEx(
        HIVES[value.hive], value.key, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, value.name, 0, TYPES[type(value.data)], value.data)


def elevate(declared: Path) -> None:
    script = str(Path(__file__).resolve())
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ELEVATE],
        env={
            **os.environ,
            "WINDOWS_SYSTEM_PYTHON": sys.executable,
            "WINDOWS_SYSTEM_ARGUMENTS": subprocess.list2cmdline(
                [script, "--declarations", str(declared)]
            ),
        },
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"elevated apply exited {result.returncode}")


def announce_environment() -> None:
    """Tell running programs, Explorer above all, that user variables changed."""
    hwnd_broadcast, wm_settingchange, smto_abortifhung = 0xFFFF, 0x1A, 0x2
    ctypes.windll.user32.SendMessageTimeoutW(
        hwnd_broadcast, wm_settingchange, 0, "Environment", smto_abortifhung, 5000, None
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--declarations", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    declared = cast(Path, args.declarations).resolve()
    timezone, values = declarations(declared)
    zone = current_timezone()
    if zone != timezone:
        print(f"windows-system: time zone: {zone!r} -> {timezone!r}")
    pending = drifted(values)
    for value in pending:
        before = current(value)
        shown = "unset" if before is None else repr(before[0])
        print(f"windows-system: {value}: {shown} -> {value.data!r}")
    if args.check:
        return
    # Users hold the time zone privilege by default, so this needs no elevation.
    if zone != timezone:
        subprocess.run(["tzutil", "/s", timezone], check=True)
        if current_timezone() != timezone:
            raise RuntimeError(f"time zone is still {current_timezone()!r}")
    if not pending:
        return
    if any(value.hive == "HKLM" for value in pending) and not (
        ctypes.windll.shell32.IsUserAnAdmin()
    ):
        elevate(declared)
    else:
        for value in pending:
            write(value)
    if remaining := drifted(pending):
        raise RuntimeError("still differs: " + ", ".join(map(str, remaining)))
    if any(value.key.casefold() == "environment" for value in pending):
        announce_environment()


if __name__ == "__main__":
    try:
        main()
    except (OSError, KeyError, ValueError, RuntimeError) as error:
        print(f"windows-system: {error}", file=sys.stderr)
        raise SystemExit(1) from error
