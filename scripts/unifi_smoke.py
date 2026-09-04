#!/usr/bin/env python3
"""Read-only smoke checks for the WAS-110 WAN path behind the UDM.

Every check is a live observation: nothing here writes to the controller. Output
is deliberately free of credentials, response payloads, public IPs, WAN MACs,
controller object IDs, and NextDNS profile IDs, so a failing run can be pasted
anywhere.
"""

from collections.abc import Callable
import contextlib
from dataclasses import dataclass, field
import ipaddress
import os
import re
import signal
import socket
import subprocess
import sys
from typing import Protocol, cast
from urllib.parse import urlparse

import httpx

DEFAULT_API_URL = "https://10.10.20.1"
NETWORK_API_PREFIX = "/proxy/network/api/s/default"
HTTP_TIMEOUT = 15.0
HTTP_OK = 200

PRIMARY_WAN_NAME = "WAS-110"
PRIMARY_WAN_GROUP = "WAN2"
BACKUP_WAN_NAME = "Internet 1"
BACKUP_WAN_GROUP = "WAN"
WAS_110_PORT_IDX = 10
WAS_110_PORT_SPEED = 10000

LCT_URL = "https://192.168.11.1"
LCT_ROUTE_NAME = "WAS-110 LCT"
LCT_ROUTE_NETWORK = "192.168.11.0/24"
LCT_ROUTE_DISTANCE = 1

NEXTDNS_TEST_URL = "https://test.nextdns.io"
CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")

DISCOVERY_COMMAND = ("dns-sd", "-B")
DISCOVERY_SERVICES = ("_airplay._tcp", "_raop._tcp", "_hap._tcp")
DISCOVERY_TIMEOUT = 6.0
DISCOVERY_SOURCE_NETWORK = ipaddress.ip_network("10.10.20.0/24")
# AirPlay and RAOP carry the assigned room name. HAP uses Apple's sensor name.
# Checking each service's actual shape avoids accepting an unrelated HomePod on
# the two protocols that can identify the room.
HOMEPOD_MARKERS = {
    "_airplay._tcp": "kitchen",
    "_raop._tcp": "kitchen",
    "_hap._tcp": "homepodsensor",
}
DNS_SD_RECORD = re.compile(r"^\S+\s+(Add|Rmv)\s+\d+\s+\d+\s+\S+\s+\S+\s+(.+)$")


class SmokeFailure(Exception):
    """A check failed. The message is safe to print."""


# --------------------------------------------------------------------------
# JSON conformance at the HTTP edge
# --------------------------------------------------------------------------


def as_mapping(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SmokeFailure(f"{what}: expected a JSON object")
    return cast(dict[str, object], value)


def as_sequence(value: object, what: str) -> list[object]:
    if not isinstance(value, list):
        raise SmokeFailure(f"{what}: expected a JSON array")
    return cast(list[object], value)


def data_records(payload: object, what: str) -> list[dict[str, object]]:
    body = as_mapping(payload, what)
    if "data" not in body:
        raise SmokeFailure(f"{what}: response has no 'data' field")
    entries = as_sequence(body["data"], f"{what} data")
    return [as_mapping(entry, f"{what} entry") for entry in entries]


def text_field(record: dict[str, object], key: str, what: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise SmokeFailure(f"{what}: '{key}' is missing or not a non-empty string")
    return value


def bool_field(record: dict[str, object], key: str, what: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise SmokeFailure(f"{what}: '{key}' is missing or not a boolean")
    return value


def int_field(record: dict[str, object], key: str, what: str) -> int:
    value = record.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise SmokeFailure(f"{what}: '{key}' is missing or not an integer")
    return value


def exactly_one(records: list[dict[str, object]], what: str) -> dict[str, object]:
    if len(records) != 1:
        raise SmokeFailure(f"{what}: expected exactly 1 match, found {len(records)}")
    return records[0]


def expect(actual: object, wanted: object, what: str) -> None:
    if actual != wanted:
        raise SmokeFailure(f"{what}: expected {wanted!r}, observed {actual!r}")


# --------------------------------------------------------------------------
# Controller access
# --------------------------------------------------------------------------


class JsonSource(Protocol):
    def get_json(self, path: str) -> object: ...


def decode_json(response: httpx.Response, what: str) -> object:
    try:
        return response.json()
    except ValueError:
        raise SmokeFailure(f"{what}: response body was not JSON") from None


@dataclass(frozen=True)
class NetworkApi:
    """Reads the legacy Network API through the UniFi OS proxy."""

    client: httpx.Client
    base_url: str

    def get_json(self, path: str) -> object:
        response = self.client.get(f"{self.base_url}{NETWORK_API_PREFIX}{path}")
        if response.status_code != HTTP_OK:
            raise SmokeFailure(f"GET {path}: HTTP {response.status_code}")
        return decode_json(response, f"GET {path}")


def login(client: httpx.Client, base_url: str, username: str, password: str) -> str:
    response = client.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password, "rememberMe": False},
    )
    if response.status_code != HTTP_OK:
        raise SmokeFailure(f"login rejected with HTTP {response.status_code}")
    if not client.cookies.jar:
        raise SmokeFailure("login returned no session cookie")
    return "authenticated to controller"


@dataclass
class UdmDevice:
    """Fetches the single UDM record once and shares it across checks."""

    api: JsonSource
    record: dict[str, object] | None = field(default=None)

    def get(self) -> dict[str, object]:
        if self.record is None:
            devices = data_records(self.api.get_json("/stat/device"), "stat/device")
            self.record = exactly_one(
                [d for d in devices if d.get("type") == "udm"], "udm device"
            )
        return self.record


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------


def wan_alive(udm: dict[str, object], group: str) -> bool:
    interfaces = as_mapping(udm.get("last_wan_interfaces"), "udm last_wan_interfaces")
    if group not in interfaces:
        raise SmokeFailure(f"udm last_wan_interfaces: no '{group}' entry")
    entry = as_mapping(interfaces[group], f"udm last_wan_interfaces.{group}")
    return bool_field(entry, "alive", f"udm last_wan_interfaces.{group}")


def check_wan_state(api: JsonSource, udm: UdmDevice) -> str:
    wans = [
        record
        for record in data_records(api.get_json("/rest/networkconf"), "networkconf")
        if record.get("purpose") == "wan"
    ]
    primary = exactly_one(
        [w for w in wans if w.get("name") == PRIMARY_WAN_NAME],
        f"WAN named {PRIMARY_WAN_NAME}",
    )
    backup = exactly_one(
        [w for w in wans if w.get("name") == BACKUP_WAN_NAME],
        f"WAN named {BACKUP_WAN_NAME}",
    )

    primary_label = f"{PRIMARY_WAN_NAME} WAN"
    expect(
        bool_field(primary, "enabled", primary_label), True, f"{primary_label} enabled"
    )
    expect(
        int_field(primary, "wan_failover_priority", primary_label),
        1,
        f"{primary_label} failover priority",
    )
    expect(
        text_field(primary, "wan_load_balance_type", primary_label),
        "weighted",
        f"{primary_label} load balance type",
    )
    expect(
        text_field(primary, "wan_networkgroup", primary_label),
        PRIMARY_WAN_GROUP,
        f"{primary_label} network group",
    )

    backup_label = f"{BACKUP_WAN_NAME} WAN"
    expect(
        int_field(backup, "wan_failover_priority", backup_label),
        2,
        f"{backup_label} failover priority",
    )
    expect(
        text_field(backup, "wan_load_balance_type", backup_label),
        "failover-only",
        f"{backup_label} load balance type",
    )
    expect(
        text_field(backup, "wan_networkgroup", backup_label),
        BACKUP_WAN_GROUP,
        f"{backup_label} network group",
    )

    device = udm.get()
    if not wan_alive(device, PRIMARY_WAN_GROUP):
        raise SmokeFailure(
            f"{PRIMARY_WAN_NAME} path ({PRIMARY_WAN_GROUP}) is not alive"
        )
    if wan_alive(device, BACKUP_WAN_GROUP):
        raise SmokeFailure(
            f"{BACKUP_WAN_NAME} path ({BACKUP_WAN_GROUP}) is alive; "
            "the supplied gateway WAN should be disconnected"
        )
    return (
        f"{PRIMARY_WAN_NAME} primary on {PRIMARY_WAN_GROUP} alive, "
        f"{BACKUP_WAN_NAME} backup on {BACKUP_WAN_GROUP} disconnected"
    )


def check_wan_public_ip(udm: UdmDevice) -> str:
    interfaces = as_mapping(
        udm.get().get("last_wan_interfaces"), "udm last_wan_interfaces"
    )
    if PRIMARY_WAN_GROUP not in interfaces:
        raise SmokeFailure(f"udm last_wan_interfaces: no '{PRIMARY_WAN_GROUP}' entry")
    entry = as_mapping(
        interfaces[PRIMARY_WAN_GROUP], f"udm last_wan_interfaces.{PRIMARY_WAN_GROUP}"
    )
    raw = text_field(entry, "ip", f"udm last_wan_interfaces.{PRIMARY_WAN_GROUP}")
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        raise SmokeFailure(
            f"{PRIMARY_WAN_GROUP} address is not a valid IP address"
        ) from None
    if not isinstance(address, ipaddress.IPv4Address):
        raise SmokeFailure(f"{PRIMARY_WAN_GROUP} address is not IPv4")
    if address in CGNAT_NETWORK:
        raise SmokeFailure(f"{PRIMARY_WAN_GROUP} address is inside CGNAT 100.64.0.0/10")
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
    ):
        raise SmokeFailure(f"{PRIMARY_WAN_GROUP} address is not publicly routable")
    return f"{PRIMARY_WAN_GROUP} holds a public, non-CGNAT IPv4 address"


def check_udm_port(udm: UdmDevice) -> str:
    ports = udm.get().get("port_table")
    records = [
        as_mapping(entry, "udm port_table entry")
        for entry in as_sequence(ports, "udm port_table")
    ]
    port = exactly_one(
        [p for p in records if p.get("port_idx") == WAS_110_PORT_IDX],
        f"udm port {WAS_110_PORT_IDX}",
    )
    label = f"udm port {WAS_110_PORT_IDX}"
    expect(int_field(port, "speed", label), WAS_110_PORT_SPEED, f"{label} speed")
    expect(bool_field(port, "full_duplex", label), True, f"{label} full duplex")
    return f"port {WAS_110_PORT_IDX} negotiated {WAS_110_PORT_SPEED} Mbps full duplex"


def check_lct_route(api: JsonSource) -> str:
    routes = data_records(api.get_json("/rest/routing"), "routing")
    route = exactly_one(
        [r for r in routes if r.get("name") == LCT_ROUTE_NAME],
        f"route named {LCT_ROUTE_NAME}",
    )
    label = f"route {LCT_ROUTE_NAME}"
    expect(bool_field(route, "enabled", label), True, f"{label} enabled")
    expect(
        text_field(route, "static-route_type", label),
        "interface-route",
        f"{label} type",
    )
    if text_field(route, "static-route_network", label) != LCT_ROUTE_NETWORK:
        raise SmokeFailure(f"{label} network does not match the expected LCT network")
    expect(
        int_field(route, "static-route_distance", label),
        LCT_ROUTE_DISTANCE,
        f"{label} distance",
    )
    return (
        f"one enabled interface route to {LCT_ROUTE_NETWORK} "
        f"at distance {LCT_ROUTE_DISTANCE}"
    )


def check_lct_https(fetch: Callable[[str], httpx.Response]) -> str:
    try:
        response = fetch(LCT_URL)
    except httpx.HTTPError as exc:
        raise SmokeFailure(f"{LCT_URL} unreachable ({type(exc).__name__})") from None
    if response.status_code != HTTP_OK:
        raise SmokeFailure(f"{LCT_URL} answered HTTP {response.status_code}")
    return f"{LCT_URL} answered HTTP {HTTP_OK}"


def check_nextdns(fetch: Callable[[str], httpx.Response]) -> str:
    try:
        response = fetch(NEXTDNS_TEST_URL)
    except httpx.HTTPError as exc:
        raise SmokeFailure(
            f"{NEXTDNS_TEST_URL} unreachable ({type(exc).__name__})"
        ) from None
    if response.status_code != HTTP_OK:
        raise SmokeFailure(f"{NEXTDNS_TEST_URL} answered HTTP {response.status_code}")

    try:
        payload = response.json()
    except ValueError:
        match = re.search(r"xhr\.open\('GET', '(https://[^']+)'", response.text)
        if match is None:
            raise SmokeFailure("nextdns test: response body was not JSON") from None
        diagnostic_url = match.group(1)
        host = urlparse(diagnostic_url).hostname
        if host is None or not host.endswith(".test.nextdns.io"):
            raise SmokeFailure("nextdns test: invalid diagnostic endpoint") from None
        try:
            response = fetch(diagnostic_url)
        except httpx.HTTPError as exc:
            raise SmokeFailure(
                f"nextdns diagnostic unreachable ({type(exc).__name__})"
            ) from None
        if response.status_code != HTTP_OK:
            raise SmokeFailure(
                f"nextdns diagnostic answered HTTP {response.status_code}"
            ) from None
        payload = decode_json(response, "nextdns diagnostic")

    body = as_mapping(payload, "nextdns test")
    expect(text_field(body, "status", "nextdns test"), "ok", "nextdns status")
    protocol = text_field(body, "protocol", "nextdns test")
    if protocol.upper() != "DOH":
        raise SmokeFailure(f"nextdns protocol: expected DoH, observed {protocol!r}")
    # The diagnostic returns a privacy-preserving profile token, not the configured
    # six-character ID. Native UDM reconciliation checks the exact ID; this endpoint
    # can only prove that the query reached some linked profile.
    _ = text_field(body, "profile", "nextdns test")
    return "resolving over DoH with a linked profile"


def dns_sd_browse(service: str) -> str:
    # `dns-sd -B` browses until killed, so the timeout is the normal exit. Its own
    # session keeps the kill from missing children that inherit the output pipe.
    process = subprocess.Popen(
        [*DISCOVERY_COMMAND, service, "local."],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        output, _ = process.communicate(timeout=DISCOVERY_TIMEOUT)
    except subprocess.TimeoutExpired:
        output = stop_browse(process)
    return output


def stop_browse(process: subprocess.Popen[str]) -> str:
    signal_group(process.pid, signal.SIGTERM)
    try:
        output, _ = process.communicate(timeout=2.0)
    except subprocess.TimeoutExpired:
        signal_group(process.pid, signal.SIGKILL)
        output, _ = process.communicate()
    return output


def signal_group(pid: int, sig: int) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pid, sig)


def local_ipv4_for(origin: str) -> str:
    host = urlparse(origin).hostname
    if host is None:
        raise SmokeFailure("controller origin has no hostname")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            connection.connect((host, 443))
            address = connection.getsockname()[0]
    except OSError as exc:
        raise SmokeFailure(
            f"could not determine discovery source network ({type(exc).__name__})"
        ) from None
    if not isinstance(address, str):
        raise SmokeFailure("could not determine discovery source network")
    return address


def current_discovery_instances(output: str) -> set[str]:
    instances: set[str] = set()
    for line in output.splitlines():
        match = DNS_SD_RECORD.match(line.strip())
        if match is None:
            continue
        action, instance = match.groups()
        if action == "Add":
            instances.add(instance.lower())
        else:
            instances.discard(instance.lower())
    return instances


def check_discovery(
    browse: Callable[[str], str], source_address: Callable[[], str] | None = None
) -> str:
    if source_address is not None:
        try:
            source = ipaddress.ip_address(source_address())
        except ValueError:
            raise SmokeFailure("discovery source is not a valid IP address") from None
        if source not in DISCOVERY_SOURCE_NETWORK:
            raise SmokeFailure("mDNS discovery must run from the YoRHa network")

    missing: list[str] = []
    for service in DISCOVERY_SERVICES:
        try:
            output = browse(service)
        except OSError as exc:
            raise SmokeFailure(
                f"dns-sd failed for {service} ({type(exc).__name__})"
            ) from None
        instances = current_discovery_instances(output)
        if not any(HOMEPOD_MARKERS[service] in instance for instance in instances):
            missing.append(service)
    if missing:
        raise SmokeFailure("Kitchen HomePod not advertised on " + ", ".join(missing))
    return "Kitchen HomePod visible on " + ", ".join(DISCOVERY_SERVICES)


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def run_check(name: str, check: Callable[[], str]) -> CheckResult:
    try:
        return CheckResult(name, True, check())
    except SmokeFailure as exc:
        return CheckResult(name, False, str(exc))
    except httpx.HTTPError as exc:
        return CheckResult(name, False, f"request failed ({type(exc).__name__})")


def report(result: CheckResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    print(f"{status}  {result.name}: {result.detail}")


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SmokeFailure(f"{name} is not set")
    return value


def controller_base_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise SmokeFailure(
            "TF_VAR_unifi_api_url must be an HTTPS origin without credentials, "
            "a path, a query, or a fragment"
        )
    return value.rstrip("/")


def main() -> int:
    try:
        username = required_env("TF_VAR_unifi_username")
        password = required_env("TF_VAR_unifi_password")
        # TF_VAR_ names are lowercase by OpenTofu convention; the default matches
        # terraform/unifi/variables.tf so an exported override still wins.
        base_url = controller_base_url(
            os.environ.get("TF_VAR_unifi_api_url", DEFAULT_API_URL)  # noqa: SIM112
        )
    except SmokeFailure as exc:
        print(f"FAIL  environment: {exc}", file=sys.stderr)
        return 1

    results: list[CheckResult] = []
    # The controller and the WAS-110 LCT both present self-signed certificates on
    # the LAN; public endpoints below keep verification on.
    with httpx.Client(verify=False, timeout=HTTP_TIMEOUT) as local:
        authenticated = run_check(
            "controller api login", lambda: login(local, base_url, username, password)
        )
        results.append(authenticated)
        report(authenticated)

        if authenticated.passed:
            api = NetworkApi(local, base_url)
            udm = UdmDevice(api)
            for name, check in (
                ("wan failover state", lambda: check_wan_state(api, udm)),
                ("wan public ipv4", lambda: check_wan_public_ip(udm)),
                ("udm port 10 link", lambda: check_udm_port(udm)),
                ("was-110 lct route", lambda: check_lct_route(api)),
            ):
                result = run_check(name, check)
                results.append(result)
                report(result)

        lct = run_check("was-110 lct https", lambda: check_lct_https(local.get))
        results.append(lct)
        report(lct)

    with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as public:
        dns = run_check("nextdns doh resolution", lambda: check_nextdns(public.get))
        results.append(dns)
        report(dns)

    discovery = run_check(
        "mdns homepod discovery",
        lambda: check_discovery(dns_sd_browse, lambda: local_ipv4_for(base_url)),
    )
    results.append(discovery)
    report(discovery)

    failed = [result for result in results if not result.passed]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
