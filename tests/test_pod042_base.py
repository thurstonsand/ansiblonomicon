from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
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


def test_pod042_mise_task_executes_expired_maintenance_through_sudo(
    tmp_path: Path,
) -> None:
    target = tmp_path / "bootstrap/targets/pod042"
    capability = tmp_path / "bootstrap/capabilities/mise"
    fake_bin = tmp_path / "bin"
    target.mkdir(parents=True)
    capability.mkdir(parents=True)
    fake_bin.mkdir()
    shutil.copy2(MISE_MAINTAIN, capability / "mise-maintain")

    updater = tmp_path / "system-mise"
    stamp = tmp_path / "cache/upgrade.stamp"
    calls = tmp_path / "calls"
    updater.write_text(f"#!/bin/sh\nprintf 'mise %s\\n' \"$*\" >> {calls}\n")
    updater.chmod(0o755)
    stamp.parent.mkdir()
    stamp.touch()
    expired = stamp.stat().st_mtime - 86401
    os.utime(stamp, (expired, expired))

    sudo = fake_bin / "sudo"
    sudo.write_text(
        f"#!/bin/sh\nprintf 'sudo %s\\n' \"$*\" >> {calls}\n"
        '[ "$1" = -n ] && shift\n'
        'if [ "$1" = install ]; then\n'
        '  for argument in "$@"; do directory=$argument; done\n'
        '  exec install -d -m 0755 "$directory"\n'
        "fi\n"
        'exec "$@"\n'
    )
    sudo.chmod(0o755)

    config = (
        (BASE.parent / "mise.toml")
        .read_text()
        .replace(
            "/usr/local/bin/mise /var/cache/ansiblonomicon/mise-upgrade.stamp",
            f"{updater} {stamp}",
        )
    )
    (target / "mise.toml").write_text(config)
    environment = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}

    subprocess.run(
        ["mise", "-C", target, "run", "mise:maintain"],
        check=True,
        env=environment,
    )

    invocation = calls.read_text()
    assert f"sudo -n {updater} self-update --yes --no-plugins" in invocation
    assert "mise self-update --yes --no-plugins" in invocation
    assert stamp.stat().st_mtime > expired
