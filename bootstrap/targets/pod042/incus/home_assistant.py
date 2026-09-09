#!/usr/bin/python3
"""Reconcile the Home Assistant OS virtual machine."""

import argparse
import hashlib
import lzma
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import time
from typing import Any
from urllib.request import urlopen

import reconcile as incus

IMAGE_VERSION = "18.2"
IMAGE_URL = (
    "https://github.com/home-assistant/operating-system/releases/download/18.2/"
    "haos_ova-18.2.qcow2.xz"
)
IMAGE_SHA256 = "254e53f354df0739e3afc09be5431a07df53f0df6b703885404f665c454f254e"
IMAGE_ALIAS = f"haos-{IMAGE_VERSION}-seed"
VM_CONFIG = {
    "limits.cpu": "4",
    "limits.memory": "8GiB",
    "security.secureboot": "false",
    "security.csm": "false",
    "boot.autostart": "true",
}
MAC = "00:16:3e:48:41:42"


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
        incus.run(
            "/usr/bin/incus",
            "image",
            "import",
            str(archive),
            str(disk),
            "--alias",
            IMAGE_ALIAS,
        )
        try:
            incus.run(
                "/usr/bin/incus",
                "init",
                IMAGE_ALIAS,
                "home-assistant",
                "--vm",
                "--storage",
                incus.POOL_NAME,
            )
        finally:
            incus.run("/usr/bin/incus", "image", "delete", IMAGE_ALIAS)


def ensure_vm(apply: bool) -> None:
    current = incus.incus_json("config", "home-assistant")
    if current is None:
        print(f"Seed home-assistant from HAOS {IMAGE_VERSION}")
        if apply:
            seed_vm()
            current = incus.incus_json("config", "home-assistant")
            assert current is not None
        else:
            raise ValueError("home-assistant instance is missing")
    if (
        current.get("type") != "virtual-machine"
        or current.get("architecture") != "x86_64"
    ):
        raise ValueError("Existing home-assistant instance has incompatible identity")
    state = incus.incus_json("info", "home-assistant")
    running = state is not None and state.get("status") == "Running"
    devices: dict[str, dict[str, Any]] = current.get("devices", {})
    root = devices.get("root", {})
    if (
        root.get("pool") != incus.POOL_NAME
        or root.get("type") != "disk"
        or root.get("path") != "/"
    ):
        raise ValueError("Existing home-assistant root storage is incompatible")
    config = current.get("config", {})
    config_drift = {
        key: value for key, value in VM_CONFIG.items() if config.get(key) != value
    }
    root_drift = root.get("size") != "64GiB"
    desired_nic = {
        "type": "nic",
        "network": "scanners",
        "hwaddr": MAC,
        "name": "eth0",
    }
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
        incus.run("/usr/bin/incus", "stop", "home-assistant")
        running = False
    for key, value in config_drift.items():
        print(f"home-assistant: {key}={value}")
        incus.run(
            "/usr/bin/incus",
            "config",
            "set",
            "home-assistant",
            f"{key}={value}",
        )
    if root_drift:
        print("home-assistant: root size=64GiB")
        incus.run(
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
            incus.run(
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
                    incus.run(
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
        incus.run("/usr/bin/incus", "start", "home-assistant")


def reconcile(mode: str) -> None:
    if os.geteuid() != 0:
        raise ValueError("Root is required")
    incus.verify_host()
    ensure_vm(mode == "apply")
    print(f"Home Assistant policy {mode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "apply"))
    reconcile(parser.parse_args().mode)


if __name__ == "__main__":
    main()
