#!/usr/bin/env python3
"""Install T3 Code, retire its vendor service, and wait for every declared instance to serve."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import tempfile
import time

HOME = Path.home()
T3 = HOME / ".local/bin/t3"
MACOS = sys.platform == "darwin"
PREFIX = "dev.mise.t3code-"
VENDOR_UNIT = (
    HOME / "Library/LaunchAgents/com.t3tools.t3code.service.plist"
    if MACOS
    else HOME / ".config/systemd/user/t3code.service"
)
# The vendor launcher's own trial deadline is long because migrations scale with the database.
READY_TIMEOUT = 600
CURL = (
    "curl",
    "-fsSL",
    "--connect-timeout",
    "20",
    "--max-time",
    "300",
    "--retry",
    "3",
    "--retry-delay",
    "10",
)


@dataclass(frozen=True)
class Instance:
    name: str
    home: Path


def run(*command: str) -> None:
    subprocess.run(command, check=True)


def output(*command: str) -> str:
    return subprocess.check_output(command, text=True)


def domain() -> str:
    return f"gui/{os.getuid()}"


def instances() -> list[Instance]:
    """Every T3 server mise declares, named t3code-<person>, with the T3CODE_HOME it serves."""
    if MACOS:
        return [
            Instance(
                plist.stem,
                Path(
                    plistlib.loads(plist.read_bytes())["EnvironmentVariables"][
                        "T3CODE_HOME"
                    ]
                ),
            )
            for plist in sorted(
                (HOME / "Library/LaunchAgents").glob(f"{PREFIX}*.plist")
            )
        ]
    found: list[Instance] = []
    for unit in sorted((HOME / ".config/systemd/user").glob(f"{PREFIX}*.service")):
        environment = output(
            "systemctl",
            "--user",
            "show",
            unit.name,
            "--property=Environment",
            "--value",
        )
        home = dict(entry.split("=", 1) for entry in environment.split())["T3CODE_HOME"]
        found.append(Instance(unit.stem, Path(home)))
    return found


def main_pid(instance: Instance) -> int:
    if MACOS:
        result = subprocess.run(
            ("launchctl", "print", f"{domain()}/{instance.name}"),
            capture_output=True,
            text=True,
        )
        match = re.search(r"^\tpid = (\d+)$", result.stdout, re.MULTILINE)
        return int(match.group(1)) if match else 0
    return int(
        output(
            "systemctl",
            "--user",
            "show",
            f"{instance.name}.service",
            "--property=MainPID",
            "--value",
        )
    )


def serving(instance: Instance) -> dict[str, object] | None:
    """The server's runtime record, once the process the service manager tracks has published it.

    The server writes it after migrations finish and HTTP binds, and removes it on a clean stop. A
    crash leaves a stale record, which the pid match rejects.
    """
    pid = main_pid(instance)
    try:
        state = json.loads((instance.home / "userdata/server-runtime.json").read_text())
    except FileNotFoundError:
        return None
    return state if pid != 0 and state["pid"] == pid else None


def installed_version() -> str | None:
    if not T3.exists():
        return None
    return output(str(T3), "--version").strip().removeprefix("t3 v")


def latest_version() -> str:
    release = output(
        *CURL,
        "-o",
        "/dev/null",
        "-w",
        "%{url_effective}",
        "https://github.com/pingdotgg/t3code/releases/latest",
    )
    return release.rsplit("/v", 1)[1]


def restart(instance: Instance) -> None:
    if MACOS:
        run("launchctl", "kickstart", "-k", f"{domain()}/{instance.name}")
    else:
        run("systemctl", "--user", "restart", f"{instance.name}.service")


def log_tail(instance: Instance) -> str:
    if MACOS:
        log = HOME / f"Library/Logs/{instance.name.removeprefix('dev.mise.')}.log"
        return "".join(log.read_text(errors="replace").splitlines(keepends=True)[-40:])
    return output(
        "journalctl",
        "--user",
        "--unit",
        f"{instance.name}.service",
        "--lines=40",
        "--no-pager",
        "--output=cat",
    )


def wait(instance: Instance) -> None:
    """Return once the instance serves, or fail with its log as soon as its server exits."""
    deadline = time.monotonic() + READY_TIMEOUT
    started = time.monotonic()
    first = main_pid(instance)
    while serving(instance) is None:
        pid = main_pid(instance)
        if (first != 0 and pid != first) or time.monotonic() > deadline:
            print(log_tail(instance), file=sys.stderr)
            raise SystemExit(
                f"{instance.name} stopped before it served; its log ends above."
                if pid != first
                else f"{instance.name} did not serve within {READY_TIMEOUT}s; its log ends above."
            )
        first = first or pid
        time.sleep(1)
    print(f"{instance.name} serves {instance.home} ({time.monotonic() - started:.1f}s)")


def require_enrollment(instance: Instance) -> None:
    # t3 prints its errors on stdout, where the JSON parser would swallow them.
    result = subprocess.run(
        (str(T3), "connect", "status", "--json", "--base-dir", str(instance.home)),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout, result.stderr, sep="", file=sys.stderr)
        raise SystemExit(f"t3 connect status failed for {instance.home}.")
    status = json.loads(result.stdout)
    if not (status["desired"] is True and status["authenticated"] is True):
        raise SystemExit(
            f"T3 enrollment missing for {instance.home}. "
            f"Run t3 connect link --headless --base-dir {instance.home} first."
        )


def prepare(check: bool) -> None:
    """Runs before mise starts the instances: they need the binary, and the vendor service holds the port."""
    current, latest = installed_version(), latest_version()
    if current != latest:
        if check:
            print(f"t3 would be installed: {current} -> {latest}")
        else:
            with tempfile.NamedTemporaryFile(suffix=".sh") as installer:
                run(*CURL, "-o", installer.name, "https://t3.codes/install.sh")
                subprocess.run(
                    ("sh", installer.name),
                    check=True,
                    env={**os.environ, "T3CODE_VERSION": latest},
                )
    if VENDOR_UNIT.exists():
        if check:
            print(f"t3's vendor service would be uninstalled: {VENDOR_UNIT}")
        else:
            run(str(T3), "service", "uninstall")
            if VENDOR_UNIT.exists():
                raise SystemExit(f"t3 service uninstall left {VENDOR_UNIT} in place.")


def apply(check: bool) -> None:
    """Moves every instance onto the installed release and its current unit, then waits for all of them."""
    version = installed_version()
    reload = not MACOS and any(
        output(
            "systemctl",
            "--user",
            "show",
            f"{instance.name}.service",
            "--property=NeedDaemonReload",
            "--value",
        ).strip()
        == "yes"
        for instance in instances()
    )
    if reload and not check:
        run("systemctl", "--user", "daemon-reload")
    for instance in instances():
        state = serving(instance)
        if reload or (state is not None and state["serverVersion"] != version):
            if check:
                print(f"{instance.name} would restart onto t3 {version}")
                continue
            restart(instance)
    if not check:
        ready()


def ready() -> None:
    """The one wait every t3 command after a restart sits behind."""
    declared = instances()
    if not declared:
        raise SystemExit(
            "No T3 instance is declared; each is a t3code-<person> unit or agent."
        )
    for instance in declared:
        wait(instance)
        require_enrollment(instance)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "apply", "ready"))
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    if arguments.action == "prepare":
        prepare(arguments.check)
    elif arguments.action == "apply":
        apply(arguments.check)
    else:
        ready()


if __name__ == "__main__":
    main()
