#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import pwd
import socket
import subprocess

HOME = Path("/home/thurstonsand")
SHIMS = HOME / ".local/share/mise/shims"
UNITS = ("t3code.service", "amp-remote.service")


def run(*command: str) -> None:
    subprocess.run(command, check=True)


def output(*command: str) -> str:
    return subprocess.check_output(command, text=True)


def require_t3() -> None:
    status = json.loads(output(str(SHIMS / "t3"), "connect", "status", "--json"))
    if not all(status[key] is True for key in ("desired", "authenticated", "linked")):
        raise SystemExit(
            "T3 enrollment missing. Run t3 connect --headless with the documented T3CODE_HOME."
        )


def require_amp() -> None:
    if not (HOME / ".local/share/amp/secrets.json").is_file():
        raise SystemExit(
            "Amp login state missing. Run amp interactively as thurstonsand first."
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("apply", "plan", "status"))
    action = parser.parse_args().action
    if (
        socket.gethostname().split(".")[0] != "pod042"
        or pwd.getpwuid(os.getuid()).pw_name != "thurstonsand"
        or os.getuid() == 0
    ):
        raise SystemExit(
            "Remote development requires pod042's normal thurstonsand user, never root."
        )
    os.environ["HOME"] = str(HOME)
    os.environ["T3CODE_HOME"] = str(HOME / ".local/share/t3code")
    os.environ["PATH"] = f"{SHIMS}:{HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"
    os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
    os.chdir(HOME)
    require_t3()
    require_amp()
    if action == "plan":
        run(str(SHIMS / "t3"), "service", "status")
        for unit in UNITS:
            run(
                "systemctl",
                "--user",
                "show",
                unit,
                "--property=LoadState,ActiveState,UnitFileState,NeedDaemonReload",
            )
        print(
            "Apply: enable operator linger if absent; vendor-idempotent t3 service install; reload and enable/start Amp, restarting only on unit changes."
        )
        return
    if action == "apply":
        if (
            output(
                "loginctl",
                "show-user",
                "thurstonsand",
                "--property=Linger",
                "--value",
            ).strip()
            != "yes"
        ):
            run("sudo", "-n", "loginctl", "enable-linger", "thurstonsand")
        changed = {
            unit: output(
                "systemctl",
                "--user",
                "show",
                unit,
                "--property=NeedDaemonReload",
                "--value",
            ).strip()
            == "yes"
            for unit in UNITS
        }
        run("systemctl", "--user", "daemon-reload")
        run(str(SHIMS / "t3"), "service", "install")
        if changed["t3code.service"]:
            run("systemctl", "--user", "restart", "t3code.service")
        run("systemctl", "--user", "enable", "amp-remote.service")
        run(
            "systemctl",
            "--user",
            "restart" if changed["amp-remote.service"] else "start",
            "amp-remote.service",
        )
    run(str(SHIMS / "t3"), "service", "status")
    if (
        output(
            "loginctl",
            "show-user",
            "thurstonsand",
            "--property=Linger",
            "--value",
        ).strip()
        != "yes"
    ):
        raise SystemExit("Operator linger is disabled.")
    for unit in UNITS:
        run("systemctl", "--user", "is-enabled", "--quiet", unit)
        run("systemctl", "--user", "is-active", "--quiet", unit)
    print(
        "Both user services are enabled and active. This is not an authenticated remote-session probe."
    )


if __name__ == "__main__":
    main()
