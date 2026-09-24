from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "bootstrap/targets/pod042/base"
MISE_MAINTAIN = ROOT / "bootstrap/capabilities/mise/mise-maintain"
SPEC = spec_from_file_location("apt_alert", BASE.parent / "alerting/apt-alert.py")
assert SPEC is not None
assert SPEC.loader is not None
apt_alert: Any = module_from_spec(SPEC)
sys.modules[SPEC.name] = apt_alert
SPEC.loader.exec_module(apt_alert)


def test_protected_package_families_exclude_kernel_and_zfs_only() -> None:
    for package in (
        "linux-image-amd64",
        "linux-headers-6.12.0-1-amd64",
        "zfsutils-linux",
        "zfs-zed",
        "libzfs6linux",
        "libzpool6linux",
        "libnvpair3linux",
        "libuutil3linux",
        "python3-pyzfs",
    ):
        assert apt_alert.is_protected_package(package)

    for package in ("curl", "openssh-server", "systemd", "docker-ce", "sanoid"):
        assert not apt_alert.is_protected_package(package)


def test_protected_upgrades_ignores_ordinary_upgrade_lines() -> None:
    simulation = """\
Inst curl [1.0] (1.1 Debian:13/stable [amd64])
Inst linux-image-amd64 [6.12] (6.13 Debian:13/stable [amd64])
Inst zfsutils-linux [2.3] (2.4 Debian:13/stable [amd64])
Conf curl (1.1 Debian:13/stable [amd64])
"""
    assert apt_alert.protected_upgrades(simulation) == [
        "linux-image-amd64",
        "zfsutils-linux",
    ]


def test_unattended_upgrades_never_touch_protected_packages_or_reboot() -> None:
    unattended = (BASE / "50unattended-upgrades").read_text()
    assert 'Automatic-Reboot "false";' in unattended
    for pattern in apt_alert.PROTECTED_PACKAGE_PATTERNS:
        assert f'"{pattern.pattern}";' in unattended


def test_mise_maintenance_skips_fresh_stamp(tmp_path: Path) -> None:
    binary = tmp_path / "mise"
    stamp = tmp_path / "cache/upgrade.stamp"
    calls = tmp_path / "calls"
    binary.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> {calls}\n")
    binary.chmod(0o755)

    subprocess.run([MISE_MAINTAIN, binary, stamp], check=True)
    subprocess.run([MISE_MAINTAIN, binary, stamp], check=True)

    assert calls.read_text() == "self-update --yes --no-plugins\n"
    assert stamp.is_file()


def test_mise_maintenance_concurrent_runs_update_once(tmp_path: Path) -> None:
    binary = tmp_path / "mise"
    stamp = tmp_path / "cache/upgrade.stamp"
    calls = tmp_path / "calls"
    binary.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> {calls}\nsleep 0.2\n")
    binary.chmod(0o755)

    processes = [subprocess.Popen([MISE_MAINTAIN, binary, stamp]) for _ in range(4)]

    assert [process.wait() for process in processes] == [0, 0, 0, 0]
    assert calls.read_text() == "self-update --yes --no-plugins\n"
    assert stamp.is_file()


def test_mise_maintenance_failure_preserves_stamp_and_retries(tmp_path: Path) -> None:
    binary = tmp_path / "mise"
    stamp = tmp_path / "cache/upgrade.stamp"
    calls = tmp_path / "calls"
    stamp.parent.mkdir()
    stamp.touch()
    expired = stamp.stat().st_mtime - 86401
    os.utime(stamp, (expired, expired))
    binary.write_text(
        f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> {calls}\n"
        f"[ $(wc -l < {calls}) -gt 1 ] || exit 19\n"
    )
    binary.chmod(0o755)

    failed = subprocess.run([MISE_MAINTAIN, binary, stamp], check=False)

    assert failed.returncode == 19
    assert stamp.stat().st_mtime == expired
    subprocess.run([MISE_MAINTAIN, binary, stamp], check=True)
    assert calls.read_text() == ("self-update --yes --no-plugins\n" * 2)
    assert stamp.stat().st_mtime > expired
