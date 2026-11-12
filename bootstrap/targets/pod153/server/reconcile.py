#!/usr/bin/env python3
"""Keep pod153 awake, reachable, and automatable with nobody at the keyboard."""

import argparse
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import time

# pod153 lives on AC power; disablesleep keeps it awake with the lid closed on either source.
AC_POWER = {
    "sleep": "0",
    "disksleep": "0",
    "displaysleep": "0",
    "standby": "0",
    "powernap": "0",
    "womp": "1",
}
CHARGE_LIMIT = 80
# Bunker gets no mDNS reflection, so the queue names the printer instead of
# browsing for it. Plain IPP, because its self-signed certificate fails IPPS.
PRINTER = ("Canon_MF650C_Series", "ipp://printer.thurstons.house/ipp/print")
TIME_MACHINE = "smb://thurstonsand@pod042.thurstons.house/timemachine"
# Time Machine copies a changed file whole, so a running Tart VM's disk image
# would go over every hour. Beeper's and Photos' databases change as often and
# both download again from their services; the rest are regenerable caches.
TIME_MACHINE_SKIPPED = [
    str(Path.home() / name)
    for name in (
        ".tart",
        ".cache",
        ".npm",
        "Library/Application Support/BeeperTexts",
        "Pictures/Photos Library.photoslibrary",
        "Library/Photos/Libraries/Syndication.photoslibrary",
    )
]
# Backups run hourly; the daily reconcile failing is what tells someone they stopped.
TIME_MACHINE_STALE = timedelta(days=1)
CUA_DRIVER = "/Applications/CuaDriver.app/Contents/MacOS/cua-driver"
CUA_DRIVER_JOB = f"gui/{os.getuid()}/dev.mise.house.thurstons.cua-driver"
SYSTEM_DAEMONS = {
    "Remote Login": ("com.openssh.sshd", "/System/Library/LaunchDaemons/ssh.plist"),
    "Tailscale": (
        "com.tailscale.tailscaled",
        "/Library/LaunchDaemons/com.tailscale.tailscaled.plist",
    ),
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


def screen_saver_idle() -> str | None:
    result = subprocess.run(
        ["defaults", "-currentHost", "read", "com.apple.screensaver", "idleTime"],
        text=True,
        capture_output=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def screen_lock_on() -> bool:
    status = subprocess.run(
        ["sysadminctl", "-screenLock", "status"], text=True, capture_output=True
    )
    return "screenLock delay is" in status.stderr


def replaced_since_start(job: str, plist: Path) -> bool:
    """Whether a running launchd job's executable, or a file its arguments name, changed after it started.

    Homebrew and self-updaters swap binaries under running services, and a pull rewrites the
    scripts some jobs run; either way the job keeps the old code until restarted. Extraction
    sets a fresh ctime even when a bottle preserves mtime.
    """
    listing = subprocess.run(
        ["launchctl", "print", job], text=True, capture_output=True
    ).stdout
    pid = re.search(r"^\tpid = (\d+)$", listing, re.MULTILINE)
    if not pid:
        return False
    executable = Path(output("ps", "-o", "comm=", "-p", pid[1]).strip()).resolve()
    started = datetime.strptime(
        subprocess.run(
            ["ps", "-o", "lstart=", "-p", pid[1]],
            check=True,
            text=True,
            capture_output=True,
            env={**os.environ, "LC_ALL": "C"},
        ).stdout.strip(),
        "%a %b %d %H:%M:%S %Y",
    )
    if not executable.exists():
        return True
    arguments = plistlib.loads(plist.read_bytes()).get("ProgramArguments", [])
    files = [executable, *(Path(a) for a in arguments[1:] if Path(a).is_absolute())]
    return any(
        file.is_file() and datetime.fromtimestamp(file.stat().st_ctime) > started
        for file in files
    )


def cua_driver_missing_grants() -> list[str]:
    """The TCC grants the running Cua Driver daemon lacks.

    `call` asks the daemon itself, so the answer is its own identity's grants, not this
    process's. A daemon launchd just started needs a moment to open its socket.
    """
    command = [CUA_DRIVER, "call", "check_permissions", '{"prompt": false}']
    result = subprocess.run(command, text=True, capture_output=True)
    for _ in range(50):
        if result.returncode == 0:
            break
        time.sleep(0.2)
        result = subprocess.run(command, text=True, capture_output=True)
    else:
        raise SystemExit(f"server: Cua Driver did not answer: {result.stderr.strip()}")
    status = json.loads(result.stdout)
    return [
        name
        for name, key in (
            ("Accessibility", "accessibility"),
            ("Screen Recording", "screen_recording"),
        )
        if not status[key]
    ]


def login_password() -> str:
    return output(os.environ["SUDO_ASKPASS"]).strip()


def samba_password() -> str:
    fnox_host = Path(__file__).resolve().parents[4] / "scripts/fnox-host"
    return output(str(fnox_host), "get", "SAMBA_MEDIA_PASSWORD").strip()


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

    sshd = output("sudo", "-n", "/usr/sbin/sshd", "-T").lower().splitlines()
    for setting in (
        "clientaliveinterval 60",
        "clientalivecountmax 3",
        "permitrootlogin no",
        "passwordauthentication no",
        "kbdinteractiveauthentication no",
    ):
        if setting not in sshd:
            raise SystemExit(f"server: effective SSH setting missing: {setting}")

    if not output("networksetup", "-getairportpower", "en0").strip().endswith("Off"):
        ethernet = output("ifconfig", "en10")
        if "status: active" not in ethernet or "inet 10.10.10.53 " not in ethernet:
            raise SystemExit(
                "server: restore Ethernet at 10.10.10.53 before disabling Wi-Fi"
            )
        changes.append(
            (
                "Wi-Fi off",
                [["sudo", "-n", "networksetup", "-setairportpower", "en0", "off"]],
            )
        )

    current = ac_power()
    drift = {key: value for key, value in AC_POWER.items() if current.get(key) != value}
    if drift:
        flags = [item for pair in drift.items() for item in pair]
        changes.append((f"AC power {drift}", [["sudo", "-n", "pmset", "-c", *flags]]))
    charge_limit = [
        "/usr/bin/osascript",
        "-l",
        "JavaScript",
        str(Path(__file__).with_name("charge_limit.js")),
    ]
    if int(output(*charge_limit)) != CHARGE_LIMIT:
        changes.append(
            (
                f"battery charge limit {CHARGE_LIMIT}%",
                [[*charge_limit, str(CHARGE_LIMIT)]],
            )
        )
    if not re.search(r"^\s*SleepDisabled\s+1$", output("pmset", "-g"), re.MULTILINE):
        changes.append(
            ("sleep disabled", [["sudo", "-n", "pmset", "-a", "disablesleep", "1"]])
        )
    # A sleeping display, a screen saver, or a locked screen hides every window from
    # accessibility and drops Screen Sharing's keys, so no agent can reach the desktop
    # until someone types the password at the Mac.
    if screen_saver_idle() != "0":
        changes.append(
            (
                "screen saver off",
                [
                    [
                        "defaults",
                        "-currentHost",
                        "write",
                        "com.apple.screensaver",
                        "idleTime",
                        "-int",
                        "0",
                    ]
                ],
            )
        )
    if screen_lock_on():
        changes.append(
            (
                "screen lock off",
                [["sysadminctl", "-screenLock", "off", "-password", "-"]],
            )
        )
    if "Restart After Freeze: On" not in output(
        "sudo", "-n", "systemsetup", "-getrestartfreeze"
    ):
        changes.append(
            (
                "restart after freeze",
                [["sudo", "-n", "systemsetup", "-setrestartfreeze", "on"]],
            )
        )
    for name, (label, plist) in SYSTEM_DAEMONS.items():
        if not daemon_loaded(label):
            changes.append(
                (
                    name,
                    [
                        ["sudo", "-n", "launchctl", "enable", f"system/{label}"],
                        ["sudo", "-n", "launchctl", "bootstrap", "system", plist],
                    ],
                )
            )
        elif replaced_since_start(f"system/{label}", Path(plist)):
            changes.append(
                (
                    f"{name} on its updated code",
                    [["sudo", "-n", "launchctl", "kickstart", "-k", f"system/{label}"]],
                )
            )
    for plist in sorted(
        (Path.home() / "Library/LaunchAgents").glob("dev.mise.*.plist")
    ):
        job = f"gui/{os.getuid()}/{plist.stem}"
        if replaced_since_start(job, plist):
            changes.append(
                (
                    f"{plist.stem} on its updated code",
                    [["launchctl", "kickstart", "-k", job]],
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
    # Through cfprefsd, because tmutil's writes reach the plist file only later.
    time_machine = plistlib.loads(
        output(
            "defaults", "export", "/Library/Preferences/com.apple.TimeMachine", "-"
        ).encode(),
        aware_datetime=True,
    )
    destinations = {
        destination["DestinationID"]: destination.get("NetworkURL")
        for destination in time_machine.get("Destinations", [])
    }
    stale_backup = None
    if list(destinations.values()) == [TIME_MACHINE]:
        latest = max(
            time_machine["Destinations"][0].get("SnapshotDates", []), default=None
        )
        if latest is None or datetime.now(UTC) - latest > TIME_MACHINE_STALE:
            stale_backup = f"server: Time Machine's last completed backup is {latest or 'none'}; see `tmutil status` and backupd's log"
    else:
        changes.append(
            (
                f"Time Machine destination {TIME_MACHINE}",
                [
                    *(
                        ["sudo", "-n", "tmutil", "removedestination", destination]
                        for destination in destinations
                    ),
                    ["sudo", "-n", "tmutil", "setdestination", "-p", TIME_MACHINE],
                ],
            )
        )
    if not time_machine.get("AutoBackup"):
        changes.append(
            ("Time Machine automatic backups", [["sudo", "-n", "tmutil", "enable"]])
        )
    skipped = set(time_machine.get("SkipPaths", []))
    if skipped != set(TIME_MACHINE_SKIPPED):
        changes.append(
            (
                f"Time Machine exclusions {TIME_MACHINE_SKIPPED}",
                [
                    *(
                        ["sudo", "-n", "tmutil", "removeexclusion", "-p", path]
                        for path in sorted(skipped - set(TIME_MACHINE_SKIPPED))
                    ),
                    *(
                        ["sudo", "-n", "tmutil", "addexclusion", "-p", path]
                        for path in sorted(set(TIME_MACHINE_SKIPPED) - skipped)
                    ),
                ],
            )
        )
    if "DOES NOT REQUIRE" not in output("automationmodetool"):
        changes.append(
            (
                "Automation Mode without authentication",
                [
                    [
                        "sudo",
                        "-n",
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
            # sysadminctl reads the password from stdin and refuses while the screen is locked.
            if command[:2] == ["sysadminctl", "-screenLock"]:
                subprocess.run(
                    command, input=login_password() + "\n", text=True, check=True
                )
            # tmutil keeps the share's password in the System keychain for backupd.
            elif command[:4] == ["sudo", "-n", "tmutil", "setdestination"]:
                subprocess.run(
                    command, input=samba_password() + "\n", text=True, check=True
                )
            else:
                subprocess.run(command, check=True)
        print(f"server: set {name}")
    # A daemon restarted under a reconcile can come up without grants TCC still
    # holds for it; starting it again picks them up.
    if missing := cua_driver_missing_grants():
        if args.check:
            print(f"server: would restart Cua Driver, which lacks {missing}")
        else:
            subprocess.run(["launchctl", "kickstart", "-k", CUA_DRIVER_JOB], check=True)
            if missing := cua_driver_missing_grants():
                raise SystemExit(
                    f"server: Cua Driver lacks {', '.join(missing)}; grant it in System Settings > Privacy & Security"
                )
            print("server: set Cua Driver on its grants")
    if stale_backup:
        raise SystemExit(stale_backup)


if __name__ == "__main__":
    main()
