#!/usr/bin/env python3
"""Power-cycle one UniFi-managed PDU outlet or PoE switch port."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
import time
from typing import Protocol, cast

import httpx

REPO_ROOT = Path.cwd()
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from unifi_api import (  # noqa: E402
    DEFAULT_API_URL,
    HTTP_OK,
    HTTP_TIMEOUT,
    NETWORK_API_PREFIX,
    ControllerError,
    NetworkApi,
    controller_base_url,
    decode_json,
    login,
    required_env,
)


class PowerCycleApi(Protocol):
    def get_json(self, path: str) -> object: ...

    def post_json(self, path: str, payload: dict[str, object]) -> object: ...

    def put_json(self, path: str, payload: dict[str, object]) -> object: ...


@dataclass(frozen=True)
class LiveApi:
    client: httpx.Client
    base_url: str

    def get_json(self, path: str) -> object:
        return NetworkApi(self.client, self.base_url).get_json(path)

    def post_json(self, path: str, payload: dict[str, object]) -> object:
        response = self.client.post(
            f"{self.base_url}{NETWORK_API_PREFIX}{path}", json=payload
        )
        if response.status_code != HTTP_OK:
            raise ControllerError(f"POST {path}: HTTP {response.status_code}")
        return decode_json(response, f"POST {path}")

    def put_json(self, path: str, payload: dict[str, object]) -> object:
        response = self.client.put(
            f"{self.base_url}{NETWORK_API_PREFIX}{path}", json=payload
        )
        if response.status_code != HTTP_OK:
            raise ControllerError(f"PUT {path}: HTTP {response.status_code}")
        return decode_json(response, f"PUT {path}")


@dataclass(frozen=True)
class Endpoint:
    kind: str
    index: int
    name: str


def mapping(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ControllerError(f"{what}: expected a JSON object")
    return cast(dict[str, object], value)


def sequence(value: object, what: str) -> list[object]:
    if not isinstance(value, list):
        raise ControllerError(f"{what}: expected a JSON array")
    return cast(list[object], value)


def records(payload: object, what: str) -> list[dict[str, object]]:
    body = mapping(payload, what)
    entries = sequence(body.get("data"), f"{what} data")
    return [mapping(entry, f"{what} entry") for entry in entries]


def text(record: dict[str, object], key: str, what: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise ControllerError(f"{what}: missing {key}")
    return value


def indexed_records(device: dict[str, object], key: str) -> list[dict[str, object]]:
    entries = sequence(device.get(key, []), f"device {key}")
    return [mapping(entry, f"device {key} entry") for entry in entries]


def select_device(api: PowerCycleApi, selector: str) -> dict[str, object]:
    devices = records(api.get_json("/stat/device"), "device listing")
    wanted = selector.casefold()
    matches = [
        device
        for device in devices
        if any(
            isinstance(device.get(field), str)
            and cast(str, device[field]).casefold() == wanted
            for field in ("name", "mac")
        )
    ]
    if len(matches) != 1:
        raise ControllerError(
            f"device selector {selector!r} matched {len(matches)} adopted devices"
        )
    return matches[0]


def find_device(api: PowerCycleApi, selector: str) -> dict[str, object]:
    device = select_device(api, selector)
    if device.get("state") != 1:
        raise ControllerError(f"device {selector!r} is not online")
    return device


def find_endpoint(device: dict[str, object], index: int) -> Endpoint:
    for outlet in indexed_records(device, "outlet_overrides"):
        if outlet.get("index") == index:
            if outlet.get("relay_state") is not True:
                raise ControllerError(f"outlet {index} is not powered")
            return Endpoint("outlet", index, text(outlet, "name", f"outlet {index}"))

    for port in indexed_records(device, "port_table"):
        if port.get("port_idx") == index:
            if port.get("poe_enable") is not True:
                raise ControllerError(f"port {index} is not supplying PoE")
            return Endpoint("PoE port", index, text(port, "name", f"port {index}"))

    raise ControllerError(f"no PDU outlet or switch port has index {index}")


def require_success(response: object, what: str) -> None:
    body = mapping(response, what)
    meta = mapping(body.get("meta"), f"{what} meta")
    if meta.get("rc") != "ok":
        raise ControllerError(f"controller rejected the {what}")


def outlet_overrides(
    device: dict[str, object], index: int, relay_state: bool
) -> list[dict[str, object]]:
    overrides = indexed_records(device, "outlet_overrides")
    updated = [dict(outlet) for outlet in overrides]
    for outlet in updated:
        if outlet.get("index") == index:
            outlet["relay_state"] = relay_state
            return updated
    raise ControllerError(f"no PDU outlet has index {index}")


def wait_for_outlet_state(
    api: PowerCycleApi,
    selector: str,
    index: int,
    relay_state: bool,
    previous_cfgversion: str,
    timeout_seconds: float = 30,
    poll_seconds: float = 1,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    while True:
        device = select_device(api, selector)
        if device.get("state") == 1:
            cfgversion = text(device, "cfgversion", f"device {selector!r}")
            outlet = next(
                (
                    outlet
                    for outlet in indexed_records(device, "outlet_table")
                    if outlet.get("index") == index
                ),
                None,
            )
            if outlet is None:
                raise ControllerError(f"no PDU outlet has index {index}")
            if (
                cfgversion != previous_cfgversion
                and device.get("known_cfgversion") == cfgversion
                and outlet.get("relay_state") is relay_state
            ):
                return cfgversion
        if time.monotonic() >= deadline:
            state = "on" if relay_state else "off"
            raise ControllerError(f"outlet {index} did not apply {state}")
        time.sleep(poll_seconds)


def power_cycle(
    api: PowerCycleApi, selector: str, index: int, pause_seconds: float = 5
) -> Endpoint:
    device = find_device(api, selector)
    endpoint = find_endpoint(device, index)
    if endpoint.kind == "outlet":
        device_id = text(device, "_id", f"device {selector!r}")
        cfgversion = text(device, "cfgversion", f"device {selector!r}")
        path = f"/rest/device/{device_id}"
        try:
            response = api.put_json(
                path,
                {"outlet_overrides": outlet_overrides(device, index, False)},
            )
            require_success(response, "outlet power-off")
            cfgversion = wait_for_outlet_state(api, selector, index, False, cfgversion)
            time.sleep(pause_seconds)
        finally:
            response = api.put_json(
                path,
                {"outlet_overrides": outlet_overrides(device, index, True)},
            )
            require_success(response, "outlet power-on")
            wait_for_outlet_state(api, selector, index, True, cfgversion)
        return endpoint

    mac = text(device, "mac", f"device {selector!r}")
    response = api.post_json(
        "/cmd/devmgr",
        {"cmd": "power-cycle", "mac": mac, "port_idx": index},
    )
    require_success(response, "PoE power-cycle")
    return endpoint


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("device", help="exact adopted-device name or MAC")
    _ = parser.add_argument("index", type=int, help="PDU outlet or PoE port index")
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        base_url = controller_base_url(DEFAULT_API_URL)
        with httpx.Client(verify=False, timeout=HTTP_TIMEOUT) as client:
            _ = login(
                client,
                base_url,
                required_env("UNIFI_USERNAME"),
                required_env("UNIFI_PASSWORD"),
            )
            endpoint = power_cycle(
                LiveApi(client, base_url), arguments.device, arguments.index
            )
        print(
            f"Power-cycled {arguments.device} {endpoint.kind} "
            f"{endpoint.index} ({endpoint.name})"
        )
        return 0
    except ControllerError as failure:
        print(f"FAIL  {failure}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
