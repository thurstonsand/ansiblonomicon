#!/usr/bin/env python3
"""Read-only answers to "what is on my network and what is it talking to".

Two sources, neither of which this script writes to: the UniFi controller knows
what is attached, where, and how it is behaving on the radio; NextDNS knows what
each device resolves. Together they identified an unlabelled pair of Espressif
boards without any access to the segment they sat on.

Everything here is a listing, so payloads are reported as observed rather than
conformed to a schema. Absent fields print as a dash instead of failing.
"""

import argparse
from collections import Counter
from dataclasses import dataclass
import sys
import time
from typing import cast

import httpx
from unifi_api import (
    DEFAULT_API_URL,
    HTTP_OK,
    HTTP_TIMEOUT,
    ControllerError,
    NetworkApi,
    controller_base_url,
    login,
    required_env,
)

NEXTDNS_API = "https://api.nextdns.io"
RANDOMIZED_NIBBLE = "26ae"


def mapping(value: object) -> dict[str, object]:
    """Anything that is not a JSON object reads as absent rather than failing."""
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def sequence(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def records(payload: object) -> list[dict[str, object]]:
    """UniFi wraps every listing in {"data": [...]}."""
    return [mapping(entry) for entry in sequence(mapping(payload).get("data"))]


def text(record: dict[str, object], *keys: str) -> str:
    """First key that holds a non-empty string, else a dash."""
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return "-"


def number(record: dict[str, object], key: str) -> int:
    value = record.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def when(record: dict[str, object], key: str) -> str:
    seconds = number(record, key)
    return time.strftime("%m-%d %H:%M", time.localtime(seconds)) if seconds else "-"


def is_randomized(mac: str) -> bool:
    """Locally administered MACs are what Apple's private Wi-Fi address looks like."""
    return len(mac) > 1 and mac[1] in RANDOMIZED_NIBBLE


@dataclass(frozen=True)
class Client:
    mac: str
    name: str
    hostname: str
    network: str
    address: str
    vendor: str
    wired: bool
    online: bool
    last_seen: str
    signal: int
    sent: int
    received: int

    @property
    def label(self) -> str:
        return self.name if self.name != "-" else self.hostname


@dataclass(frozen=True)
class Controller:
    api: NetworkApi

    def networks(self) -> dict[str, str]:
        return {
            text(record, "_id"): text(record, "name")
            for record in records(self.api.get_json("/rest/networkconf"))
        }

    def devices(self) -> list[dict[str, object]]:
        return records(self.api.get_json("/stat/device"))

    def clients(self, *, history: bool) -> list[Client]:
        names = self.networks()
        live = {
            text(record, "mac"): record
            for record in records(self.api.get_json("/stat/sta"))
        }
        known = (
            records(self.api.get_json("/stat/alluser"))
            if history
            else list(live.values())
        )
        seen: dict[str, Client] = {}
        for record in known:
            mac = text(record, "mac")
            current = live.get(mac)
            source = current or record
            seen[mac] = Client(
                mac=mac,
                name=text(record, "name"),
                hostname=text(record, "hostname"),
                network=names.get(text(source, "network_id"), text(source, "network")),
                address=text(source, "ip"),
                vendor=text(record, "oui"),
                wired=source.get("is_wired") is True,
                online=current is not None,
                last_seen=when(source, "last_seen"),
                signal=number(source, "signal"),
                sent=number(source, "rx_bytes"),
                received=number(source, "tx_bytes"),
            )
        return sorted(seen.values(), key=lambda c: (c.network, c.address, c.label))


@dataclass(frozen=True)
class NextDns:
    client: httpx.Client
    profile: str

    def get(self, path: str, **params: str | int) -> object:
        response = self.client.get(
            f"{NEXTDNS_API}/profiles/{self.profile}{path}", params=params
        )
        if response.status_code != HTTP_OK:
            raise ControllerError(f"nextdns {path}: HTTP {response.status_code}")
        payload: object = response.json()
        return payload

    def devices(self) -> list[dict[str, object]]:
        return records(self.get("/analytics/devices", **{"from": "-30d", "limit": 200}))

    def identify(self, address: str, window: str) -> tuple[str, Counter[str]]:
        """Find the NextDNS device behind a LAN address and what it resolves."""
        name, domains = "-", Counter[str]()
        cursor: str | None = None
        for _ in range(10):
            params: dict[str, str | int] = {"limit": 1000, "from": window}
            if cursor is not None:
                params["cursor"] = cursor
            payload = mapping(self.get("/logs", **params))
            entries = [mapping(entry) for entry in sequence(payload.get("data"))]
            for entry in entries:
                device = mapping(entry.get("device"))
                if device.get("localIp") != address:
                    continue
                name = text(device, "name", "id")
                domains[text(entry, "domain")] += 1
            page = mapping(mapping(payload.get("meta")).get("pagination")).get("cursor")
            cursor = page if isinstance(page, str) else None
            if cursor is None or not entries:
                break
        return name, domains


def show_clients(controller: Controller, *, history: bool, unnamed_only: bool) -> None:
    clients = controller.clients(history=history)
    if unnamed_only:
        clients = [client for client in clients if client.name == "-"]
    print(
        f"{'network':12s} {'address':15s} {'mac':17s} {'name':34s} {'how':6s} "
        f"{'seen':12s} vendor"
    )
    for client in clients:
        how = (
            "wired"
            if client.wired
            else f"{client.signal} dBm"
            if client.signal
            else "wifi"
        )
        seen = "online" if client.online else client.last_seen
        flag = " [randomized]" if is_randomized(client.mac) else ""
        print(
            f"{client.network:12s} {client.address:15s} {client.mac:17s} {client.label:34s} "
            f"{how:6s} {seen:12s} {client.vendor}{flag}"
        )
    print(f"\n{len(clients)} clients")


def show_devices(controller: Controller) -> None:
    for device in sorted(controller.devices(), key=lambda d: text(d, "name")):
        print(
            f"  {text(device, 'name'):24s} {text(device, 'model'):9s} "
            f"{text(device, 'ip'):15s} {text(device, 'mac')}"
        )


def show_traffic(nextdns: NextDns, address: str, window: str) -> None:
    name, domains = nextdns.identify(address, window)
    print(f"{address} is {name!r} in NextDNS over {window}")
    if not domains:
        print("  no queries in the window; it may resolve elsewhere or be silent")
        return
    for domain, count in domains.most_common(40):
        print(f"  {count:6d}  {domain}")


def show_nextdns_devices(nextdns: NextDns) -> None:
    for device in nextdns.devices():
        print(
            f"  {text(device, 'id'):8s} {text(device, 'name'):34s} "
            f"{text(device, 'model'):24s} {number(device, 'queries')}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    clients = commands.add_parser("clients", help="what is attached, by network")
    _ = clients.add_argument(
        "--history", action="store_true", help="include clients seen but now offline"
    )
    _ = clients.add_argument(
        "--unnamed", action="store_true", help="only clients with no controller name"
    )

    _ = commands.add_parser("devices", help="adopted UniFi hardware")

    traffic = commands.add_parser(
        "traffic", help="what one address resolves, by domain"
    )
    _ = traffic.add_argument("address", help="a LAN address, e.g. 10.10.40.187")
    _ = traffic.add_argument(
        "--window", default="-7d", help="NextDNS window, default -7d"
    )

    _ = commands.add_parser(
        "resolvers", help="devices NextDNS has seen, by query volume"
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        if arguments.command in ("clients", "devices"):
            base_url = controller_base_url(DEFAULT_API_URL)
            with httpx.Client(verify=False, timeout=HTTP_TIMEOUT) as client:
                _ = login(
                    client,
                    base_url,
                    required_env("UNIFI_USERNAME"),
                    required_env("UNIFI_PASSWORD"),
                )
                controller = Controller(NetworkApi(client, base_url))
                if arguments.command == "clients":
                    show_clients(
                        controller,
                        history=arguments.history,
                        unnamed_only=arguments.unnamed,
                    )
                else:
                    show_devices(controller)
            return 0

        key = required_env("NEXTDNS_API_KEY")
        profile = required_env("NEXTDNS_PROFILE_ID")
        with httpx.Client(timeout=60.0, headers={"X-Api-Key": key}) as client:
            nextdns = NextDns(client, profile)
            if arguments.command == "traffic":
                show_traffic(nextdns, arguments.address, arguments.window)
            else:
                show_nextdns_devices(nextdns)
        return 0
    except ControllerError as failure:
        print(f"FAIL  {failure}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
