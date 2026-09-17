#!/usr/bin/env python3
"""Terminate the client VLANs inside a namespace that holds nothing else.

pod042 is the only machine in the house that can watch a segment from inside it,
which is what diagnosing discovery, DHCP or roaming problems takes. Giving the host
itself an address on each VLAN would answer that need and expose every wildcard
listener it has: sshd, Caddy, Plex, Scrypted all bind to any address the host holds.

So the tags terminate in `probe` instead. It has one macvlan leg per VLAN, each with
its own identity in the controller, no default route, no forwarding and no veth back
to the root namespace. Nothing on a client VLAN can reach a pod042 service or route
through it, and an agent that forgets the wrapper gets "network unreachable" rather
than quietly probing from the service host.

Bridge mode matters: macvlan isolates a parent from its own children, so a non-bridge
leg could not reach the Home Assistant VM, whose interface is parented on the same
VLAN 40 link.
"""

from dataclasses import dataclass
import subprocess

NAMESPACE = "probe"
PARENT = "enp5s0"


@dataclass(frozen=True)
class Leg:
    name: str
    vlan: int
    address: str
    mac: str

    @property
    def parent(self) -> str:
        return f"{PARENT}.{self.vlan}"


LEGS = (
    Leg("yorha", 20, "10.10.20.251/24", "02:00:0a:0a:14:fb"),
    Leg("lunar-tear", 30, "10.10.30.251/24", "02:00:0a:0a:1e:fb"),
    Leg("scanners", 40, "10.10.40.251/24", "02:00:0a:0a:28:fb"),
    Leg("village", 50, "10.10.50.251/24", "02:00:0a:0a:32:fb"),
)


def run(*command: str) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)


def exists(*command: str) -> bool:
    return subprocess.run(command, capture_output=True).returncode == 0


def ensure_namespace() -> None:
    if not exists("ip", "netns", "pid", NAMESPACE):
        run("ip", "netns", "add", NAMESPACE)
    run("ip", "-n", NAMESPACE, "link", "set", "lo", "up")
    run("ip", "netns", "exec", NAMESPACE, "sysctl", "-q", "net.ipv4.ip_forward=0")


def ensure_parent(leg: Leg) -> None:
    """The VLAN link in the root namespace, which never carries an address.

    IPv6 is disabled on it because an addressless interface still takes a link-local
    address, and the host's services listen on [::].
    """
    if not exists("ip", "link", "show", leg.parent):
        run(
            "ip", "link", "add", "link", PARENT,
            "name", leg.parent, "type", "vlan", "id", str(leg.vlan),
        )  # fmt: skip
    run("sysctl", "-q", f"net.ipv6.conf.{leg.parent.replace('.', '/')}.disable_ipv6=1")
    run("ip", "link", "set", leg.parent, "up")


def ensure_leg(leg: Leg) -> None:
    if not exists("ip", "-n", NAMESPACE, "link", "show", leg.name):
        if exists("ip", "link", "show", leg.name):
            run("ip", "link", "delete", leg.name)
        run(
            "ip", "link", "add", leg.name, "link", leg.parent,
            "address", leg.mac, "type", "macvlan", "mode", "bridge",
        )  # fmt: skip
        run("ip", "link", "set", leg.name, "netns", NAMESPACE)
    run("ip", "-n", NAMESPACE, "address", "replace", leg.address, "dev", leg.name)
    run("ip", "-n", NAMESPACE, "link", "set", leg.name, "up")


def main() -> None:
    ensure_namespace()
    for leg in LEGS:
        ensure_parent(leg)
        ensure_leg(leg)
    print("probe namespace holds " + ", ".join(leg.name for leg in LEGS))


if __name__ == "__main__":
    main()
