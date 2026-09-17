#!/usr/bin/env python3
import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import pwd
import socket
import subprocess
import tomllib

HOME = Path("/home/thurstonsand")
SHIMS = HOME / ".local/share/mise/shims"
HERDR = SHIMS / "herdr"
UNITS = ("t3code.service", "amp-remote.service", "herdr.service")

# operator:tools installs T3's CLI into its own prefix and records there why it can be
# neither a global install nor an npx invocation. Read that inventory rather than repeating
# its paths: the service's own copy of them lives in the t3-operator.conf drop-in, which
# systemd requires as literals, and two homes for a path are already one too many.
T3_INVENTORY = tomllib.loads(
    (Path(__file__).parents[1] / "operator/node-packages.toml").read_text()
)["prefixed"]["t3"]
T3 = Path(T3_INVENTORY["prefix"]) / "node_modules/.bin/t3"
T3_NPMRC = T3_INVENTORY["npmrc"]


def run(*command: str) -> None:
    subprocess.run(command, check=True)


def output(*command: str) -> str:
    return subprocess.check_output(command, text=True)


def require_t3() -> None:
    status = json.loads(output(str(T3), "connect", "status", "--json"))
    if not all(status[key] is True for key in ("desired", "authenticated")):
        raise SystemExit(
            "T3 enrollment missing. Run t3 connect --headless as thurstonsand first."
        )


def require_amp() -> None:
    if not (HOME / ".local/share/amp/secrets.json").is_file():
        raise SystemExit(
            "Amp login state missing. Run amp login as thurstonsand first."
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
    os.environ["NPM_CONFIG_USERCONFIG"] = T3_NPMRC
    os.environ["PATH"] = (
        f"{HOME}/.local/bin:{HOME}/.amp/bin:{HOME}/.opencode/bin:"
        f"{SHIMS}:/usr/local/bin:/usr/bin:/bin"
    )
    os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
    os.chdir(HOME)
    require_t3()
    require_amp()
    require_herdr()
    if action == "plan":
        run(str(T3), "service", "status")
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
            "Apply: enable operator linger if absent; vendor-idempotent t3 service install; "
            "stop any Herdr server systemd does not own, losing its panes; start all three "
            "services, restarting on unit changes and on a stale Herdr binary."
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
        run(str(T3), "service", "install")
        run(
            "systemctl",
            "--user",
            "restart" if changed["t3code.service"] else "start",
            "t3code.service",
        )
        run("systemctl", "--user", "enable", "amp-remote.service")
        run(
            "systemctl",
            "--user",
            "restart" if changed["amp-remote.service"] else "start",
            "amp-remote.service",
        )
        # A Herdr client that finds no socket spawns its own server, which then owns the
        # socket and holds the login session's kernel keyring. Logging out revokes that
        # keyring and every agent credential store reading through it. Handing the socket
        # to systemd means stopping that server, and its panes go with it.
        herdr = herdr_server()
        if herdr.running and not unit_active("herdr.service"):
            print("Stopping a Herdr server systemd does not own; its panes end here.")
            run(str(HERDR), "server", "stop")
        run("systemctl", "--user", "enable", "herdr.service")
        run(
            "systemctl",
            "--user",
            "restart" if changed["herdr.service"] or herdr.binary_stale else "start",
            "herdr.service",
        )
    run(str(T3), "service", "status")
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
