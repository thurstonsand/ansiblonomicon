from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import tomllib
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "bootstrap/targets/pod042/base"
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


def test_base_declaration_matches_accepted_contract() -> None:
    config = tomllib.loads((BASE.parent / "mise.base.toml").read_text())
    bootstrap = config["bootstrap"]
    packages = bootstrap["packages"]
    for package in (
        "intel-microcode",
        "locales",
        "systemd-timesyncd",
        "unattended-upgrades",
    ):
        assert packages[f"apt:{package}"] == "latest"

    ssh = bootstrap["files"]["/etc/ssh/sshd_config.d/00-ansiblonomicon.conf"]["content"]
    assert ssh == (
        "ClientAliveCountMax 3\n"
        "ClientAliveInterval 30\n"
        "PasswordAuthentication no\n"
        "PermitRootLogin no\n"
        "PrintLastLog yes\n"
        "PubkeyAuthentication yes\n"
    )
    assert bootstrap["files"]["/etc/ssh/sshd_config.d/00-ansiblonomicon.conf"][
        "notify"
    ] == ["ssh"]
    assert bootstrap["services"]["apt-daily-upgrade.timer"] == {
        "state": "running",
        "enabled": True,
    }

    unattended = (BASE / "50unattended-upgrades").read_text()
    assert '"origin=*";' in unattended
    for setting in (
        "Automatic-Reboot",
        "Remove-Unused-Kernel-Packages",
        "Remove-New-Unused-Dependencies",
        "Remove-Unused-Dependencies",
    ):
        assert f'{setting} "false";' in unattended
    for pattern in apt_alert.PROTECTED_PACKAGE_PATTERNS:
        assert f'"{pattern.pattern}";' in unattended
    journal = (BASE / "journald.conf").read_text()
    assert "Storage=persistent" in journal
    assert "SystemMaxUse=1G" in journal
    assert "MaxRetentionSec=30day" in journal
