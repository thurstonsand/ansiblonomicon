#!/usr/bin/env python3
"""Verify pod042's live physical network contract."""

import json
from pathlib import Path
import subprocess
from typing import Any, cast

INTERFACE = "enp5s0"
MAC = "a0:36:bc:28:37:41"
ADDRESS = "10.10.10.42"
GATEWAY = "10.10.10.1"


def output(*command: str) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def verify(
    links: list[dict[str, Any]],
    addresses: list[dict[str, Any]],
    routes: list[dict[str, Any]],
    resolver: str,
    ipv4_forwarding: str,
    ipv6_forwarding: str,
    ethernet: str,
    rings: str,
) -> list[str]:
    errors: list[str] = []
    links_by_name = {str(link["ifname"]): link for link in links}
    physical = links_by_name.get(INTERFACE)
    if physical is None:
        return [f"missing physical interface {INTERFACE}"]
    if physical.get("address") != MAC:
        errors.append(f"{INTERFACE} does not have expected MAC {MAC}")
    if physical.get("mtu") != 1500:
        errors.append(f"{INTERFACE} MTU is not 1500")
    if physical.get("operstate") != "UP":
        errors.append(f"{INTERFACE} link is not up")
    if physical.get("master") is not None:
        errors.append(f"{INTERFACE} must not be enslaved to a host bridge")
    if "br0" in links_by_name:
        errors.append("retired host bridge br0 still exists")

    addresses_by_name = {str(interface["ifname"]): interface for interface in addresses}
    physical_addresses = cast(
        list[dict[str, Any]],
        addresses_by_name.get(INTERFACE, {}).get("addr_info", []),
    )
    ipv4 = [
        address for address in physical_addresses if address.get("family") == "inet"
    ]
    if len(ipv4) != 1 or ipv4[0].get("local") != ADDRESS:
        errors.append(f"{INTERFACE} does not have sole IPv4 address {ADDRESS}")
    elif not ipv4[0].get("dynamic", False):
        errors.append(f"{INTERFACE} IPv4 address is not DHCP-managed")
    global_ipv6 = [
        address
        for address in physical_addresses
        if address.get("family") == "inet6" and address.get("scope") == "global"
    ]
    if global_ipv6:
        errors.append(f"{INTERFACE} has unexpected routed IPv6")
    wifi_addresses = cast(
        list[dict[str, Any]],
        addresses_by_name.get("wlo1", {}).get("addr_info", []),
    )
    if wifi_addresses:
        errors.append("wlo1 must not have an address")

    defaults = [route for route in routes if route.get("dst") == "default"]
    if len(defaults) != 1:
        errors.append("expected exactly one default route")
    elif defaults[0].get("dev") != INTERFACE or defaults[0].get("gateway") != GATEWAY:
        errors.append(f"default route must use {GATEWAY} through {INTERFACE}")
    if not any(
        line.strip() == f"nameserver {GATEWAY}" for line in resolver.splitlines()
    ):
        errors.append(f"resolver does not use {GATEWAY}")
    if ipv4_forwarding.strip() != "1":
        errors.append("IPv4 forwarding is not enabled")
    if ipv6_forwarding.strip() != "0":
        errors.append("IPv6 forwarding must remain disabled")
    if "Speed: 2500Mb/s" not in ethernet:
        errors.append(f"{INTERFACE} did not negotiate 2.5 Gb/s")
    if "Link detected: yes" not in ethernet:
        errors.append(f"{INTERFACE} has no carrier")
    if "Wake-on: g" not in ethernet:
        errors.append(f"{INTERFACE} magic-packet wake is not enabled")
    current_rings = rings.partition("Current hardware settings:")[2]
    if not any(
        line.startswith("RX:") and line.partition(":")[2].strip() == "4096"
        for line in current_rings.splitlines()
    ):
        errors.append(f"{INTERFACE} RX ring is not 4096 entries")
    return errors


def main() -> int:
    errors = verify(
        json.loads(output("/usr/sbin/ip", "-json", "link", "show")),
        json.loads(output("/usr/sbin/ip", "-json", "address", "show")),
        json.loads(output("/usr/sbin/ip", "-json", "route", "show", "table", "main")),
        Path("/etc/resolv.conf").read_text(),
        output("/usr/sbin/sysctl", "-n", "net.ipv4.ip_forward"),
        output("/usr/sbin/sysctl", "-n", "net.ipv6.conf.all.forwarding"),
        output("/usr/sbin/ethtool", INTERFACE),
        output("/usr/sbin/ethtool", "-g", INTERFACE),
    )
    if errors:
        for error in errors:
            print(f"FAIL  {error}")
        return 1
    print(
        f"PASS  {INTERFACE} {ADDRESS} via {GATEWAY}, "
        "2.5 Gb/s, MTU 1500, RX ring 4096, WOL enabled"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
