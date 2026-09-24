from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import tomllib
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "bootstrap/targets/pod042"
MODULE_PATH = TARGET / "network/check.py"
SPEC = spec_from_file_location("pod042_network_check", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
network_check: Any = module_from_spec(SPEC)
sys.modules[SPEC.name] = network_check
# check.py reads the leg definitions from probe.py, its neighbour on the target.
with patch.object(sys, "path", [str(TARGET / "network"), *sys.path]):
    SPEC.loader.exec_module(network_check)
probe: Any = sys.modules["probe"]


def good_state() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    str,
    str,
    str,
    str,
    str,
    dict[str, str],
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
        {"IPv4": "DROP", "IPv6": "DROP"},
    )


def test_container_forwarding_is_paired_with_a_drop_policy() -> None:
    bootstrap = tomllib.loads((TARGET / "mise.network.toml").read_text())["bootstrap"]
    sysctl = bootstrap["files"]["/etc/sysctl.d/90-pod042-network.conf"]["content"]
    assert "net.ipv4.ip_forward = 1" in sysctl
    assert "net.ipv6.conf.all.forwarding = 0" in sysctl
    # Forwarding is on for container NAT, so routing must be denied by policy.
    assert bootstrap["services"]["forward-policy"] == {
        "state": "running",
        "enabled": True,
    }
    unit = (TARGET / "network/forward-policy.service").read_text()
    assert "--policy FORWARD DROP" in unit
    assert "ip6tables --policy FORWARD DROP" in unit


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
        "AdvertiseTags": ["tag:pod042"],
        "ExitNodeID": "",
        "ExitNodeIP": "",
        "RunSSH": True,
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
        "RunSSH": False,
    }

    assert network_check.verify_tailscale(status, preferences) == [
        "Tailscale is not online",
        "Tailscale node name is not pod042",
        "Tailscale IPv4 address is not 100.64.249.18",
        "Tailscale DNS acceptance must remain disabled",
        "Tailscale route acceptance must remain disabled",
        "Tailscale must not advertise routes",
        "Tailscale must advertise only tag:pod042",
        "Tailscale must not use an exit node",
        "Tailscale SSH must be enabled",
    ]


def test_live_network_contract_reports_boundary_drift() -> None:
    links, addresses, routes, resolver, _, _, ethernet, rings, _ = good_state()
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
        {"IPv4": "ACCEPT", "IPv6": "DROP"},
    )
    assert errors == [
        "enp5s0 must not be enslaved to a host bridge",
        "host bridge br0 exists; containers must attach to the physical NIC",
        "enp5s0 does not have sole IPv4 address 10.10.10.42",
        "wlo1 must not have an address",
        "default route must use 10.10.10.1 through enp5s0",
        "IPv4 forwarding is not enabled",
        "IPv6 forwarding must remain disabled",
        "IPv4 FORWARD policy is ACCEPT, not DROP",
        "enp5s0 magic-packet wake is not enabled",
        "enp5s0 RX ring is not 4096 entries",
    ]


def probe_state() -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], str, list[dict[str, Any]]
]:
    legs: list[dict[str, Any]] = [
        {
            "ifname": leg.name,
            "addr_info": [
                {
                    "family": "inet",
                    "local": leg.address.split("/")[0],
                    "prefixlen": int(leg.address.split("/")[1]),
                }
            ],
        }
        for leg in probe.LEGS
    ]
    routes: list[dict[str, Any]] = [
        {"dst": "10.10.20.0/24", "dev": "yorha"},
        {"dst": "10.10.40.0/24", "dev": "scanners"},
    ]
    root: list[dict[str, Any]] = [
        {"ifname": "enp5s0", "addr_info": [{"family": "inet", "local": "10.10.10.42"}]},
        *({"ifname": leg.parent, "addr_info": []} for leg in probe.LEGS),
    ]
    return legs, routes, "0\n", root


def test_probe_namespace_terminates_every_client_vlan() -> None:
    assert network_check.verify_probe(*probe_state()) == []


def test_probe_namespace_contract_reports_drift() -> None:
    legs, routes, forwarding, root = probe_state()
    assert network_check.verify_probe(legs[1:], routes, forwarding, root) == [
        "probe namespace is missing the yorha leg"
    ]

    wrong = [dict(leg) for leg in legs]
    wrong[0]["addr_info"] = [
        {"family": "inet", "local": "10.10.20.99", "prefixlen": 24}
    ]
    assert network_check.verify_probe(wrong, routes, forwarding, root) == [
        f"probe leg yorha does not hold {probe.LEGS[0].address}"
    ]

    routed = [*routes, {"dst": "default", "gateway": "10.10.20.1", "dev": "yorha"}]
    assert network_check.verify_probe(legs, routed, forwarding, root) == [
        "probe namespace must not have a default route"
    ]
    assert network_check.verify_probe(legs, routes, "1\n", root) == [
        "probe namespace must not forward"
    ]

    leaked = [dict(interface) for interface in root]
    leaked[1]["addr_info"] = [{"family": "inet", "local": "10.10.20.251"}]
    assert network_check.verify_probe(legs, routes, forwarding, leaked) == [
        f"{probe.LEGS[0].parent} must stay addressless in the root namespace"
    ]

    host_address: list[dict[str, Any]] = [dict(interface) for interface in root]
    host_address[0]["addr_info"] = [{"family": "inet", "local": "10.10.40.251"}]
    assert network_check.verify_probe(legs, routes, forwarding, host_address) == [
        "enp5s0 holds client VLAN address 10.10.40.251 in root"
    ]
