#!/usr/bin/python3
"""Reconcile the small Incus substrate and the fresh Home Assistant VM."""

import argparse
import grp
import hashlib
import json
import lzma
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time
from typing import Any, cast
from urllib.request import urlopen

IMAGE_VERSION = "18.2"
IMAGE_URL = (
    "https://github.com/home-assistant/operating-system/releases/download/18.2/"
    "haos_ova-18.2.qcow2.xz"
)
IMAGE_SHA256 = "254e53f354df0739e3afc09be5431a07df53f0df6b703885404f665c454f254e"
IMAGE_ALIAS = f"haos-{IMAGE_VERSION}-seed"
POOL = {"driver": "dir", "source": "/mnt/black-box/agents/incus"}
NETWORK = {"type": "macvlan", "parent": "enp5s0", "vlan": "40"}
VM_CONFIG = {
    "limits.cpu": "4",
    "limits.memory": "8GiB",
    "security.secureboot": "false",
    "security.csm": "false",
    "boot.autostart": "true",
}
MAC = "00:16:3e:48:41:42"


def run(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, capture_output=capture, text=True)


def output(*args: str) -> str:
    return run(*args, capture=True).stdout.strip()


def incus_json(kind: str, name: str) -> dict[str, Any] | None:
    collections = {
        "storage": "storage-pools",
        "network": "networks",
        "config": "instances",
        "info": "instances",
    }
    suffix = "/state" if kind == "info" else ""
    arguments = [
        "/usr/bin/incus",
        "query",
        f"/1.0/{collections[kind]}/{name}{suffix}",
    ]
    result = subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        if "not found" in result.stderr.lower():
            return None
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr
        )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError(f"Unexpected Incus {kind} response")
    return cast(dict[str, Any], value)


def ensure_access(apply: bool) -> None:
    group = grp.getgrnam("incus-admin")
    groups = {item.gr_name for item in grp.getgrall() if "thurstonsand" in item.gr_mem}
    if group.gr_name not in groups:
        print("Add thurstonsand to incus-admin")
        if not apply:
            raise ValueError("thurstonsand is not in incus-admin")
        run("/usr/sbin/usermod", "-aG", "incus-admin", "thurstonsand")


def ensure_pool(apply: bool) -> None:
    current = incus_json("storage", "local")
    if current is None:
        print("Create Incus dir pool local")
        if apply:
            run(
                "/usr/bin/incus",
                "storage",
                "create",
                "local",
                "dir",
                f"source={POOL['source']}",
            )
        else:
            raise ValueError("Incus storage pool local is missing")
        return
    config = current.get("config", {})
    if (
        current.get("driver") != POOL["driver"]
        or config.get("source") != POOL["source"]
    ):
        raise ValueError("Existing Incus storage pool local has incompatible identity")


def ensure_network(apply: bool) -> None:
    current = incus_json("network", "scanners")
    if current is None:
        print("Create Incus macvlan network scanners")
        if apply:
            run(
                "/usr/bin/incus",
                "network",
                "create",
                "scanners",
                "--type=macvlan",
                "parent=enp5s0",
                "vlan=40",
            )
        else:
            raise ValueError("Incus network scanners is missing")
        return
    config = current.get("config", {})
    actual = {
        "type": current.get("type"),
        **{key: config.get(key) for key in ("parent", "vlan")},
    }
    if current.get("managed") is not True or actual != NETWORK:
        raise ValueError("Existing Incus network scanners has incompatible identity")


def seed_vm() -> None:
    with tempfile.TemporaryDirectory(prefix="haos-seed-") as temporary:
        root = Path(temporary)
        compressed = root / "disk.qcow2.xz"
        digest = hashlib.sha256()
        with (
            urlopen(IMAGE_URL, timeout=60) as response,
            compressed.open("wb") as target,
        ):
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                target.write(chunk)
        if digest.hexdigest() != IMAGE_SHA256:
            raise ValueError("Home Assistant seed checksum mismatch")
        disk = root / "rootfs.img"
        with lzma.open(compressed) as source, disk.open("wb") as target:
            shutil.copyfileobj(source, target)
        metadata = root / "metadata.yaml"
        metadata.write_text(
            f"architecture: x86_64\ncreation_date: {int(time.time())}\n"
            f"properties:\n  description: Home Assistant OS {IMAGE_VERSION} seed\n"
        )
        archive = root / "metadata.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(metadata, arcname="metadata.yaml")
        run(
            "/usr/bin/incus",
            "image",
            "import",
            str(archive),
            str(disk),
            "--alias",
            IMAGE_ALIAS,
        )
        try:
            run(
                "/usr/bin/incus",
                "init",
                IMAGE_ALIAS,
                "home-assistant",
                "--vm",
                "--storage",
                "local",
            )
        finally:
            run("/usr/bin/incus", "image", "delete", IMAGE_ALIAS)


def ensure_vm(apply: bool) -> None:
    current = incus_json("config", "home-assistant")
    if current is None:
        print(f"Seed home-assistant from HAOS {IMAGE_VERSION}")
        if apply:
            seed_vm()
            current = incus_json("config", "home-assistant")
            assert current is not None
        else:
            raise ValueError("home-assistant instance is missing")
    if (
        current.get("type") != "virtual-machine"
        or current.get("architecture") != "x86_64"
    ):
        raise ValueError("Existing home-assistant instance has incompatible identity")
    state = incus_json("info", "home-assistant")
    running = state is not None and state.get("status") == "Running"
    devices = current.get("devices", {})
    root = devices.get("root", {})
    if (
        root.get("pool") != "local"
        or root.get("type") != "disk"
        or root.get("path") != "/"
    ):
        raise ValueError("Existing home-assistant root storage is incompatible")
    config = current.get("config", {})
    config_drift = {
        key: value for key, value in VM_CONFIG.items() if config.get(key) != value
    }
    root_drift = root.get("size") != "64GiB"
    desired_nic = {"type": "nic", "network": "scanners", "hwaddr": MAC, "name": "eth0"}
    nic = devices.get("eth0")
    if nic is not None and (
        nic.get("type") != "nic" or nic.get("network") != "scanners"
    ):
        raise ValueError("Existing home-assistant NIC has incompatible identity")
    nic_drift = nic is None or any(
        nic.get(key) != value for key, value in desired_nic.items()
    )
    if not apply and (config_drift or root_drift or nic_drift or not running):
        raise ValueError("home-assistant instance differs from its declaration")
    if apply and running and (config_drift or root_drift or nic_drift):
        print("Stop home-assistant for configuration")
        run("/usr/bin/incus", "stop", "home-assistant")
        running = False
    for key, value in config_drift.items():
        print(f"home-assistant: {key}={value}")
        run(
            "/usr/bin/incus",
            "config",
            "set",
            "home-assistant",
            f"{key}={value}",
        )
    if root_drift:
        print("home-assistant: root size=64GiB")
        run(
            "/usr/bin/incus",
            "config",
            "device",
            "set",
            "home-assistant",
            "root",
            "size=64GiB",
        )
    if nic_drift:
        print("home-assistant: device eth0")
        if nic is None:
            run(
                "/usr/bin/incus",
                "config",
                "device",
                "add",
                "home-assistant",
                "eth0",
                "nic",
                "network=scanners",
                f"hwaddr={MAC}",
                "name=eth0",
            )
        else:
            for key in ("hwaddr", "name"):
                if nic.get(key) != desired_nic[key]:
                    run(
                        "/usr/bin/incus",
                        "config",
                        "device",
                        "set",
                        "home-assistant",
                        "eth0",
                        f"{key}={desired_nic[key]}",
                    )
    if not running:
        print("Start home-assistant")
        run("/usr/bin/incus", "start", "home-assistant")


def verify_host() -> None:
    version = output("/usr/bin/dpkg-query", "-W", "-f=${Version}", "incus")
    if not version.startswith("6.0"):
        raise ValueError(f"Incus 6.0 LTS required, found {version}")
    if output("/usr/bin/systemctl", "is-active", "incus") != "active":
        raise ValueError("Incus service is not running")
    if output("/usr/bin/systemctl", "is-enabled", "incus.socket") != "enabled":
        raise ValueError("Incus socket is not enabled")
    if output("/usr/bin/systemctl", "is-enabled", "incus-startup.service") != "enabled":
        raise ValueError("Incus startup service is not enabled")
    if not os.access("/dev/kvm", os.R_OK | os.W_OK):
        raise ValueError("KVM is unavailable")


def reconcile(mode: str) -> None:
    if os.geteuid() != 0:
        raise ValueError("Root is required")
    apply = mode == "apply"
    verify_host()
    ensure_access(apply)
    ensure_pool(apply)
    ensure_network(apply)
    ensure_vm(apply)
    print(f"Incus policy {mode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "apply"))
    reconcile(parser.parse_args().mode)


if __name__ == "__main__":
    main()
