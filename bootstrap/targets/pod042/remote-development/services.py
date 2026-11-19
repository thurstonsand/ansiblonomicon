#!/usr/bin/env python3
import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import pwd
import socket
import subprocess
import sys

HOME = Path("/home/thurstonsand")
SHIMS = HOME / ".local/share/mise/shims"
HERDR = SHIMS / "herdr"
HERDR_UNIT = "dev.mise.herdr.service"
UNITS = (
    "dev.mise.amp-remote.service",
    "dev.mise.claude-remote-control.service",
    HERDR_UNIT,
    "dev.mise.chatgpt.service",
    "chatgpt-upgrade.path",
    "dev.mise.1password.service",
)
T3_READY = Path(__file__).resolve().parents[1] / "t3/t3.py"


def run(*command: str) -> None:
    subprocess.run(command, check=True)


def output(*command: str) -> str:
    return subprocess.check_output(command, text=True)


def require_t3() -> None:
    run(sys.executable, str(T3_READY), "ready")


def require_amp() -> None:
    if not (HOME / ".local/share/amp/secrets.json").is_file():
        raise SystemExit(
            "Amp login state missing. Run amp login as thurstonsand first."
        )


def require_claude() -> None:
    if "claudeAiOauth" not in (HOME / ".claude/.credentials.json").read_text():
        raise SystemExit(
            "Claude login missing. Run claude auth login --claudeai as thurstonsand first."
        )


def require_chatgpt() -> None:
    if not (HOME / ".codex/auth.json").is_file():
        raise SystemExit(
            "ChatGPT login state missing. Run codex login as thurstonsand first."
        )


def require_herdr() -> None:
    if not os.access(HERDR, os.X_OK):
        raise SystemExit(
            "Herdr shim missing. Reconcile the operator config before this one."
        )


@dataclass(frozen=True)
class HerdrServer:
    running: bool
    binary_stale: bool


def herdr_server() -> HerdrServer:
    status = json.loads(output(str(HERDR), "status", "server", "--json"))
    return HerdrServer(
        running=status["running"], binary_stale=status["server_binary_stale"]
    )


def unit_active(unit: str) -> bool:
    return (
        subprocess.run(("systemctl", "--user", "is-active", "--quiet", unit)).returncode
        == 0
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
    os.environ["PATH"] = (
        f"{HOME}/.local/bin:{HOME}/.amp/bin:{SHIMS}:/usr/local/bin:/usr/bin:/bin"
    )
    os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
    os.chdir(HOME)
    require_t3()
    require_amp()
    require_claude()
    require_chatgpt()
    require_herdr()
    if action == "plan":
        for unit in UNITS:
            run(
                "systemctl",
                "--user",
                "show",
                unit,
                "--property=LoadState,ActiveState,UnitFileState,NeedDaemonReload",
            )
        # Subprocess output is unbuffered where print is not, so an unflushed line here
        # would surface after everything the loop above wrote.
        print(json.dumps(asdict(herdr_server())), flush=True)
        print(
            "Apply: enable operator linger if absent; start the ChatGPT upgrade watch, "
            "restarting it on unit changes; stop any "
            "Herdr server systemd does not own, losing its panes, and restart Herdr on a "
            "stale binary. Mise applies the Amp, Claude, Herdr, ChatGPT, and 1Password units."
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
        changed = (
            output(
                "systemctl",
                "--user",
                "show",
                "chatgpt-upgrade.path",
                "--property=NeedDaemonReload",
                "--value",
            ).strip()
            == "yes"
        )
        run("systemctl", "--user", "daemon-reload")
        run("systemctl", "--user", "enable", "chatgpt-upgrade.path")
        run(
            "systemctl",
            "--user",
            "restart" if changed else "start",
            "chatgpt-upgrade.path",
        )
        run("systemctl", "--user", "start", "chatgpt-upgrade.service")
        # A Herdr client that finds no socket spawns its own server, which then owns the
        # socket and holds the login session's kernel keyring. Logging out revokes that
        # keyring and every agent credential store reading through it. Handing the socket
        # to systemd means stopping that server, and its panes go with it.
        herdr = herdr_server()
        if herdr.running and not unit_active(HERDR_UNIT):
            print("Stopping a Herdr server systemd does not own; its panes end here.")
            run(str(HERDR), "server", "stop")
        run(
            "systemctl",
            "--user",
            "restart" if herdr.binary_stale else "start",
            HERDR_UNIT,
        )
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
        "Systemd startup checks passed, not remote readiness. Verify live connections and check for subsequent crashes before declaring completion."
    )


if __name__ == "__main__":
    main()
