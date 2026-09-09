#!/usr/bin/python3
"""Reconcile the Incus substrate used by pod042 workloads."""

import argparse
import grp
import json
import os
import subprocess
from typing import Any, cast

POOL_NAME = "black-box"
POOL = {"driver": "dir", "source": "/mnt/black-box/incus"}
NETWORK = {"type": "macvlan", "parent": "enp5s0", "vlan": "40"}


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
    current = incus_json("storage", POOL_NAME)
    if current is None:
        print(f"Create Incus dir pool {POOL_NAME}")
        if apply:
            run(
                "/usr/bin/incus",
                "storage",
                "create",
                POOL_NAME,
                "dir",
                f"source={POOL['source']}",
            )
        else:
            raise ValueError(f"Incus storage pool {POOL_NAME} is missing")
        return
    config = current.get("config", {})
    if (
        current.get("driver") != POOL["driver"]
        or config.get("source") != POOL["source"]
    ):
        raise ValueError(
            f"Existing Incus storage pool {POOL_NAME} has incompatible identity"
        )


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
    print(f"Incus policy {mode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "apply"))
    reconcile(parser.parse_args().mode)


if __name__ == "__main__":
    main()
