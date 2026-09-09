#!/usr/bin/python3
"""Verify pod042's live base-host contract."""

from pathlib import Path
import subprocess

PACKAGES = (
    "intel-microcode",
    "locales",
    "openssh-server",
    "systemd-timesyncd",
    "unattended-upgrades",
)
EXPECTED_FILES = {
    "/etc/systemd/journald.conf.d/00-ansiblonomicon.conf": (
        "[Journal]\nStorage=persistent\nSystemMaxUse=1G\nMaxRetentionSec=30day\n"
    ),
    "/etc/apt/apt.conf.d/20auto-upgrades": (
        'APT::Periodic::Update-Package-Lists "1";\n'
        'APT::Periodic::Unattended-Upgrade "1";\n'
    ),
}


def output(*command: str) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def active(unit: str) -> bool:
    return (
        subprocess.run(
            ["/usr/bin/systemctl", "is-active", "--quiet", unit], check=False
        ).returncode
        == 0
    )


def enabled(unit: str) -> bool:
    return (
        subprocess.run(
            ["/usr/bin/systemctl", "is-enabled", "--quiet", unit], check=False
        ).returncode
        == 0
    )


def main() -> int:
    errors: list[str] = []
    for package in PACKAGES:
        status = subprocess.run(
            ["/usr/bin/dpkg-query", "-W", "-f=${db:Status-Abbrev}", package],
            check=False,
            capture_output=True,
            text=True,
        )
        if status.returncode or status.stdout != "ii ":
            errors.append(f"package {package} is not installed")

    if "en_US.utf8" not in output("/usr/bin/locale", "-a").splitlines():
        errors.append("locale en_US.UTF-8 is not generated")
    timedate = output(
        "/usr/bin/timedatectl",
        "show",
        "--property=Timezone",
        "--property=NTPSynchronized",
    )
    if "Timezone=America/New_York" not in timedate:
        errors.append("timezone is not America/New_York")
    if "NTPSynchronized=yes" not in timedate:
        errors.append("system clock is not synchronized")

    for unit in ("ssh.service", "systemd-timesyncd.service"):
        if not active(unit) or not enabled(unit):
            errors.append(f"{unit} is not active and enabled")
    if not active("apt-daily-upgrade.timer") or not enabled("apt-daily-upgrade.timer"):
        errors.append("apt-daily-upgrade.timer is not active and enabled")

    sshd = output("/usr/sbin/sshd", "-T").lower().splitlines()
    for setting in (
        "passwordauthentication no",
        "permitrootlogin no",
        "pubkeyauthentication yes",
        "clientaliveinterval 30",
        "clientalivecountmax 3",
        "printlastlog yes",
    ):
        if setting not in sshd:
            errors.append(f"effective SSH setting missing: {setting}")

    for name, expected in EXPECTED_FILES.items():
        path = Path(name)
        if not path.exists() or path.read_text() != expected:
            errors.append(f"base configuration differs from its declaration: {name}")

    unattended = Path("/etc/apt/apt.conf.d/50unattended-upgrades")
    required_unattended_settings = (
        '"origin=*";',
        '"^linux-.*";',
        '"^zfs.*";',
        'Remove-Unused-Kernel-Packages "false";',
        'Remove-New-Unused-Dependencies "false";',
        'Remove-Unused-Dependencies "false";',
        'Automatic-Reboot "false";',
    )
    unattended_text = unattended.read_text() if unattended.exists() else ""
    for setting in required_unattended_settings:
        if setting not in unattended_text:
            errors.append(f"unattended-upgrades setting missing: {setting}")

    if errors:
        for error in errors:
            print(f"FAIL  {error}")
        return 1
    print("PASS  base packages, locale, time, SSH, journal, and upgrades")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
