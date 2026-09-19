from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "agents/homelab/skills/surveying-the-network/scripts/power_cycle.py"
)
SPEC = spec_from_file_location("network_power_cycle", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
with patch.object(
    sys, "path", [str(Path(__file__).resolve().parents[1] / "scripts"), *sys.path]
):
    SPEC.loader.exec_module(MODULE)

ControllerError: type[Exception] = MODULE.ControllerError


class FakeApi:
    def __init__(
        self,
        devices: list[dict[str, object]],
        responses: list[object] | None = None,
        states: list[int] | None = None,
    ) -> None:
        self.devices = devices
        self.responses = responses or []
        self.states = states or []
        self.reads = 0
        self.cfgversion = 0
        self.writes: list[tuple[str, str, dict[str, object]]] = []

    def get_json(self, path: str) -> object:
        assert path == "/stat/device"
        self.reads += 1
        if self.states:
            self.devices[0]["state"] = self.states.pop(0)
        return {"data": self.devices}

    def post_json(self, path: str, payload: dict[str, object]) -> object:
        self.writes.append(("POST", path, payload))
        return self.responses.pop(0) if self.responses else {"meta": {"rc": "ok"}}

    def put_json(self, path: str, payload: dict[str, object]) -> object:
        self.writes.append(("PUT", path, payload))
        device_id = path.rsplit("/", 1)[-1]
        device = next(
            device for device in self.devices if device.get("_id") == device_id
        )
        self.cfgversion += 1
        device["outlet_overrides"] = payload["outlet_overrides"]
        device["outlet_table"] = payload["outlet_overrides"]
        device["cfgversion"] = str(self.cfgversion)
        device["known_cfgversion"] = str(self.cfgversion)
        return self.responses.pop(0) if self.responses else {"meta": {"rc": "ok"}}


def test_power_cycles_named_pdu_outlet() -> None:
    api = FakeApi(
        [
            {
                "name": "USP PDU Pro",
                "mac": "d8:b3:70:2c:b7:45",
                "_id": "pdu-id",
                "state": 1,
                "cfgversion": "0",
                "known_cfgversion": "0",
                "outlet_table": [
                    {
                        "index": 1,
                        "name": "Hue Bridge Pro",
                        "relay_state": True,
                        "cycle_enabled": False,
                    },
                    {"index": 2, "name": "Other", "relay_state": True},
                ],
                "outlet_overrides": [
                    {
                        "index": 1,
                        "name": "Hue Bridge Pro",
                        "relay_state": True,
                        "cycle_enabled": False,
                    },
                    {"index": 2, "name": "Other", "relay_state": True},
                ],
            }
        ]
    )

    endpoint = MODULE.power_cycle(api, "USP PDU Pro", 1, pause_seconds=0)

    assert endpoint == MODULE.Endpoint("outlet", 1, "Hue Bridge Pro")
    assert api.reads == 3
    assert api.writes == [
        (
            "PUT",
            "/rest/device/pdu-id",
            {
                "outlet_overrides": [
                    {
                        "index": 1,
                        "name": "Hue Bridge Pro",
                        "relay_state": False,
                        "cycle_enabled": False,
                    },
                    {"index": 2, "name": "Other", "relay_state": True},
                ]
            },
        ),
        (
            "PUT",
            "/rest/device/pdu-id",
            {
                "outlet_overrides": [
                    {
                        "index": 1,
                        "name": "Hue Bridge Pro",
                        "relay_state": True,
                        "cycle_enabled": False,
                    },
                    {"index": 2, "name": "Other", "relay_state": True},
                ]
            },
        ),
    ]


def test_refuses_unpowered_outlet_without_sending_command() -> None:
    api = FakeApi(
        [
            {
                "name": "USP PDU Pro",
                "mac": "d8:b3:70:2c:b7:45",
                "state": 1,
                "outlet_table": [
                    {
                        "index": 1,
                        "name": "Hue Bridge Pro",
                        "relay_state": True,
                    }
                ],
                "outlet_overrides": [
                    {"index": 1, "name": "Hue Bridge Pro", "relay_state": False}
                ],
            }
        ]
    )

    with pytest.raises(ControllerError, match="outlet 1 is not powered"):
        _ = MODULE.power_cycle(api, "USP PDU Pro", 1)

    assert not api.writes


def test_refuses_non_poe_switch_port_without_sending_command() -> None:
    api = FakeApi(
        [
            {
                "name": "USW Pro Max 24 PoE",
                "mac": "f4:e2:c6:ab:91:02",
                "state": 1,
                "port_table": [
                    {"port_idx": 2, "name": "Hue Bridge Pro", "poe_enable": False}
                ],
            }
        ]
    )

    with pytest.raises(ControllerError, match="port 2 is not supplying PoE"):
        _ = MODULE.power_cycle(api, "USW Pro Max 24 PoE", 2)

    assert not api.writes


def test_requires_an_exact_unique_device_selector() -> None:
    api = FakeApi(
        [
            {
                "name": "USP PDU Pro",
                "mac": "d8:b3:70:2c:b7:45",
                "state": 1,
            }
        ]
    )

    with pytest.raises(ControllerError, match="matched 0 adopted devices"):
        _ = MODULE.power_cycle(api, "PDU", 1)

    assert not api.writes


def test_rejects_controller_failure() -> None:
    api = FakeApi(
        [
            {
                "name": "USW Pro Max 24 PoE",
                "mac": "f4:e2:c6:ab:91:02",
                "state": 1,
                "port_table": [
                    {
                        "port_idx": 3,
                        "name": "SuperLink Gateway",
                        "poe_enable": True,
                    }
                ],
            }
        ],
        [{"meta": {"rc": "error"}}],
    )

    with pytest.raises(ControllerError, match="rejected the PoE power-cycle"):
        _ = MODULE.power_cycle(api, "USW Pro Max 24 PoE", 3)

    assert len(api.writes) == 1


def test_restores_pdu_power_when_power_off_response_is_rejected() -> None:
    api = FakeApi(
        [
            {
                "name": "USP PDU Pro",
                "mac": "d8:b3:70:2c:b7:45",
                "_id": "pdu-id",
                "state": 1,
                "cfgversion": "0",
                "known_cfgversion": "0",
                "outlet_overrides": [
                    {
                        "index": 1,
                        "name": "Hue Bridge Pro",
                        "relay_state": True,
                    }
                ],
            }
        ],
        [{"meta": {"rc": "error"}}, {"meta": {"rc": "ok"}}],
    )

    with pytest.raises(ControllerError, match="outlet power-off"):
        _ = MODULE.power_cycle(api, "USP PDU Pro", 1, pause_seconds=0)

    assert api.reads == 2
    assert len(api.writes) == 2
    assert api.writes[-1][2]["outlet_overrides"] == [
        {"index": 1, "name": "Hue Bridge Pro", "relay_state": True}
    ]


def test_waits_through_pdu_provisioning_disconnect() -> None:
    api = FakeApi(
        [
            {
                "name": "USP PDU Pro",
                "mac": "d8:b3:70:2c:b7:45",
                "_id": "pdu-id",
                "state": 1,
                "cfgversion": "0",
                "known_cfgversion": "0",
                "outlet_table": [
                    {"index": 1, "name": "Hue Bridge Pro", "relay_state": True}
                ],
                "outlet_overrides": [
                    {"index": 1, "name": "Hue Bridge Pro", "relay_state": True}
                ],
            }
        ],
        states=[1, 0, 1, 1],
    )

    with patch.object(MODULE.time, "sleep") as sleep:
        endpoint = MODULE.power_cycle(api, "USP PDU Pro", 1, pause_seconds=0)

    assert endpoint == MODULE.Endpoint("outlet", 1, "Hue Bridge Pro")
    assert api.reads == 4
    sleep.assert_any_call(1)
