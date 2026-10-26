#!/usr/bin/env python3
"""Keep pod153 awake, reachable, and automatable with nobody at the keyboard."""

import argparse
import re
import subprocess

# pod153 lives on AC power; disablesleep keeps it awake with the lid closed on either source.
AC_POWER = {
    "sleep": "0",
    "disksleep": "0",
    "standby": "0",
    "powernap": "0",
    "womp": "1",
}
# Bunker gets no mDNS reflection, so the queue names the printer instead of
# browsing for it. Plain IPP, because its self-signed certificate fails IPPS.
PRINTER = ("Canon_MF650C_Series", "ipp://printer.thurstons.house/ipp/print")
SYSTEM_DAEMONS = {
    "Remote Login": ("com.openssh.sshd", "/System/Library/LaunchDaemons/ssh.plist"),
}


def output(*command: str) -> str:
    return subprocess.run(command, check=True, text=True, capture_output=True).stdout


def ac_power() -> dict[str, str]:
    section = output("pmset", "-g", "custom").split("AC Power:", 1)[1]
    return dict(re.findall(r"^\s+(\w+)\s+(\S+)$", section, re.MULTILINE))


def daemon_loaded(label: str) -> bool:
    result = subprocess.run(
        ["launchctl", "print", f"system/{label}"],
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changes: list[tuple[str, list[list[str]]]] = []

    # Only the System Settings toggle grants com.apple.screensharing.agent Screen
    # Recording and event posting; started through launchctl, Screen Sharing shows
    # the login window black and drops every key, so pod153-wake cannot log in.
    if not daemon_loaded("com.apple.screensharing"):
        raise SystemExit(
            "server: Screen Sharing is off; turn it on in System Settings > General > Sharing"
        )

    current = ac_power()
    drift = {key: value for key, value in AC_POWER.items() if current.get(key) != value}
    if drift:
        flags = [item for pair in drift.items() for item in pair]
        changes.append((f"AC power {drift}", [["pmset", "-c", *flags]]))
    if not re.search(r"^\s*SleepDisabled\s+1$", output("pmset", "-g"), re.MULTILINE):
        changes.append(("sleep disabled", [["pmset", "-a", "disablesleep", "1"]]))
    if "Restart After Freeze: On" not in output(
        "sudo", "-n", "systemsetup", "-getrestartfreeze"
    ):
        changes.append(
            ("restart after freeze", [["systemsetup", "-setrestartfreeze", "on"]])
        )
    for name, (label, plist) in SYSTEM_DAEMONS.items():
        if not daemon_loaded(label):
            changes.append(
                (
                    name,
                    [
                        ["launchctl", "enable", f"system/{label}"],
                        ["launchctl", "bootstrap", "system", plist],
                    ],
                )
            )
    printer, uri = PRINTER
    device = subprocess.run(
        ["lpstat", "-v", printer], text=True, capture_output=True
    ).stdout
    if f"device for {printer}: {uri}" not in device:
        driver = [] if device else ["-m", "everywhere"]
        changes.append(
            (
                f"printer {printer}",
                [["lpadmin", "-p", printer, "-E", "-v", uri, *driver]],
            )
        )
    if "DOES NOT REQUIRE" not in output("automationmodetool"):
        changes.append(
            (
                "Automation Mode without authentication",
                [
                    [
                        "automationmodetool",
                        "enable-automationmode-without-authentication",
                    ]
                ],
            )
        )

    for name, commands in changes:
        if args.check:
            print(f"server: would set {name}")
            continue
        for command in commands:
            subprocess.run(["sudo", "-n", *command], check=True)
        print(f"server: set {name}")


if __name__ == "__main__":
    main()
