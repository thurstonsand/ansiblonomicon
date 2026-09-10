from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import tomllib
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "bootstrap/targets/pod042"
MODULE_PATH = TARGET / "network/check.py"
SPEC = spec_from_file_location("pod042_network_check", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
network_check: Any = module_from_spec(SPEC)
sys.modules[SPEC.name] = network_check
SPEC.loader.exec_module(network_check)


def good_state() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    str,
    str,
    str,
    str,
    str,
]:
    links: list[dict[str, Any]] = [
        {
            "ifname": "enp5s0",
            "address": "a0:36:bc:28:37:41",
            "mtu": 1500,
            "operstate": "UP",
        },
        {"ifname": "wlo1", "mtu": 1500, "operstate": "DOWN"},
    ]
    addresses: list[dict[str, Any]] = [
        {
            "ifname": "enp5s0",
            "addr_info": [
                {
                    "family": "inet",
                    "local": "10.10.10.42",
                    "scope": "global",
                    "dynamic": True,
                },
                {"family": "inet6", "local": "fe80::1", "scope": "link"},
            ],
        },
        {"ifname": "wlo1", "addr_info": []},
    ]
    routes: list[dict[str, Any]] = [
        {
            "dst": "default",
            "gateway": "10.10.10.1",
            "dev": "enp5s0",
            "protocol": "dhcp",
        },
        {"dst": "10.10.10.0/24", "dev": "enp5s0", "protocol": "dhcp"},
    ]
    ethernet = "Speed: 2500Mb/s\nWake-on: g\nLink detected: yes\n"
    rings = "Current hardware settings:\nRX:\t\t\t4096\nTX:\t\t\t256\n"
    return (
        links,
        addresses,
        routes,
        "nameserver 10.10.10.1\n",
        "1\n",
        "0\n",
        ethernet,
        rings,
    )


def test_network_declaration_owns_physical_contract_and_retirement() -> None:
    config = tomllib.loads((TARGET / "mise.network.toml").read_text())
    bootstrap = config["bootstrap"]
    interfaces = bootstrap["files"]["/etc/network/interfaces"]["content"]
    assert "auto enp5s0" in interfaces
    assert "allow-hotplug enp5s0" not in interfaces
    assert "iface enp5s0 inet dhcp" in interfaces
    assert "mtu 1500" in interfaces
    assert "ethtool -s enp5s0 wol g" in interfaces
    assert "ethtool -G enp5s0 rx 4096" in interfaces
    assert "wlo1" not in interfaces
    sysctl = bootstrap["files"]["/etc/sysctl.d/90-pod042-network.conf"]["content"]
    assert "net.ipv4.ip_forward = 1" in sysctl
    assert "net.ipv6.conf.all.forwarding = 0" in sysctl
    retired = {
        path
        for path, declaration in bootstrap["files"].items()
        if declaration.get("state") == "absent"
    }
    assert retired == {
        "/etc/systemd/network/10-br0.netdev",
        "/etc/systemd/network/10-br0.network",
        "/etc/systemd/network/11-nic.network",
        "/etc/systemd/network/21-br0.1.netdev",
        "/etc/systemd/network/21-br0.1.network",
        "/etc/systemd/network/22-br0.2.netdev",
        "/etc/systemd/network/22-br0.2.network",
        "/etc/systemd/network/23-br0.3.netdev",
        "/etc/systemd/network/23-br0.3.network",
        "/etc/systemd/network/24-br0.4.netdev",
        "/etc/systemd/network/24-br0.4.network",
    }


def test_live_network_contract_accepts_expected_state() -> None:
    assert network_check.verify(*good_state()) == []


def test_tailscale_contract_accepts_direct_route_free_node() -> None:
    status = {
        "BackendState": "Running",
        "Self": {
            "DNSName": "pod042.tail5f024.ts.net.",
            "Online": True,
            "TailscaleIPs": ["100.64.249.18", "fd7a:115c:a1e0::f82f:f913"],
        },
    }
    preferences = {
        "CorpDNS": False,
        "RouteAll": False,
        "AdvertiseRoutes": None,
        "AdvertiseTags": None,
        "ExitNodeID": "",
        "ExitNodeIP": "",
    }

    assert network_check.verify_tailscale(status, preferences) == []


def test_tailscale_contract_reports_authority_drift() -> None:
    status = {
        "BackendState": "Stopped",
        "Self": {
            "DNSName": "wrong.tail5f024.ts.net.",
            "Online": False,
            "TailscaleIPs": ["100.100.100.100"],
        },
    }
    preferences = {
        "CorpDNS": True,
        "RouteAll": True,
        "AdvertiseRoutes": ["0.0.0.0/0"],
        "AdvertiseTags": ["tag:server"],
        "ExitNodeID": "node-id",
        "ExitNodeIP": "100.100.100.101",
    }

    assert network_check.verify_tailscale(status, preferences) == [
        "Tailscale is not online",
        "Tailscale node name is not pod042",
        "Tailscale IPv4 address is not 100.64.249.18",
        "Tailscale DNS acceptance must remain disabled",
        "Tailscale route acceptance must remain disabled",
        "Tailscale must not advertise routes",
        "Tailscale must not advertise tags",
        "Tailscale must not use an exit node",
    ]


def test_live_network_contract_reports_boundary_drift() -> None:
    links, addresses, routes, resolver, _, _, ethernet, rings = good_state()
    links[0]["master"] = "br0"
    links.append({"ifname": "br0", "mtu": 1500, "operstate": "UP"})
    addresses[0]["addr_info"][0]["local"] = "10.10.10.187"
    addresses[1]["addr_info"] = [
        {"family": "inet", "local": "10.10.10.188", "scope": "global"}
    ]
    routes[0]["gateway"] = "10.10.10.254"
    errors = network_check.verify(
        links,
        addresses,
        routes,
        resolver,
        "0\n",
        "1\n",
        ethernet.replace("Wake-on: g", "Wake-on: d"),
        rings.replace("RX:\t\t\t4096", "RX:\t\t\t256"),
    )
    assert errors == [
        "enp5s0 must not be enslaved to a host bridge",
        "retired host bridge br0 still exists",
        "enp5s0 does not have sole IPv4 address 10.10.10.42",
        "wlo1 must not have an address",
        "default route must use 10.10.10.1 through enp5s0",
        "IPv4 forwarding is not enabled",
        "IPv6 forwarding must remain disabled",
        "enp5s0 magic-packet wake is not enabled",
        "enp5s0 RX ring is not 4096 entries",
    ]
