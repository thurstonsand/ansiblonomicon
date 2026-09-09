#!/usr/bin/python3
"""Send actionable APT state to Hark through the shared alerting shim."""

from pathlib import Path
import re
import subprocess
import sys

PROTECTED_PACKAGE_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"^linux-.*",
        r"^zfs.*",
        r"^libzfs.*",
        r"^libzpool.*",
        r"^libnvpair.*",
        r"^libuutil.*",
        r"^python3-pyzfs$",
    )
)


def is_protected_package(package: str) -> bool:
    return any(pattern.fullmatch(package) for pattern in PROTECTED_PACKAGE_PATTERNS)


def protected_upgrades(apt_simulation: str) -> list[str]:
    packages = {
        fields[1]
        for line in apt_simulation.splitlines()
        if line.startswith("Inst ")
        and len(fields := line.split()) > 1
        and is_protected_package(fields[1])
    }
    return sorted(packages)


def alert(title: str, body: str) -> int:
    return subprocess.run(
        ["/usr/local/bin/storage-alert", title, body], check=False
    ).returncode


def post_upgrade() -> int:
    simulation = subprocess.run(
        ["/usr/bin/apt-get", "--simulate", "dist-upgrade"],
        check=False,
        capture_output=True,
        text=True,
    )
    if simulation.returncode != 0:
        return alert(
            "APT follow-up check failed",
            "apt-get --simulate dist-upgrade failed after unattended upgrades",
        )

    status = 0
    protected = protected_upgrades(simulation.stdout)
    if protected:
        status |= alert(
            "Protected updates pending",
            "Kernel/ZFS packages require deliberate reconciliation: "
            + ", ".join(protected),
        )
    reboot_required = Path("/run/reboot-required")
    if reboot_required.exists():
        detail = reboot_required.read_text().strip() or "reboot-required is present"
        status |= alert("Reboot required", detail)
    return status


def main(argv: list[str]) -> int:
    if argv == ["post-upgrade"]:
        return post_upgrade()
    if len(argv) == 2 and argv[0] == "failure":
        return alert(
            "Automatic upgrade failed",
            f"{argv[1]} failed; inspect journalctl -u {argv[1]}",
        )
    print("usage: pod042-apt-alert post-upgrade | failure UNIT", file=sys.stderr)
    return 64


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
