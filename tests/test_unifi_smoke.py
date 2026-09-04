from collections.abc import Callable
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import time
from typing import Any

import httpx
import pytest
from pytest import CaptureFixture, MonkeyPatch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/unifi_smoke.py"
SPEC = spec_from_file_location("unifi_smoke", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

SmokeFailure: type[Exception] = MODULE.SmokeFailure

# Values that must never reach stdout, stderr, or an exception message.
PUBLIC_IP = "99.93.14.108"
WAN_MAC = "0a:e0:d0:11:22:33"
CONTROLLER_ID = "6a96f3c8e7da43f704f0bd87"
NEXTDNS_PROFILE = "dad2bs2e1jou95tj9h70"
PASSWORD = "hunter2-not-in-output"
SECRETS = (PUBLIC_IP, WAN_MAC, CONTROLLER_ID, NEXTDNS_PROFILE, PASSWORD)


class FakeApi:
    """Serves canned Network API payloads and records the paths requested."""

    def __init__(self, payloads: dict[str, object]) -> None:
        self.payloads = payloads
        self.paths: list[str] = []

    def get_json(self, path: str) -> object:
        self.paths.append(path)
        if path not in self.payloads:
            raise SmokeFailure(f"GET {path}: HTTP 404")
        return self.payloads[path]


def wan_configs() -> object:
    return {
        "data": [
            {
                "_id": CONTROLLER_ID,
                "name": "WAS-110",
                "purpose": "wan",
                "enabled": True,
                "wan_failover_priority": 1,
                "wan_load_balance_type": "weighted",
                "wan_networkgroup": "WAN2",
            },
            {
                "_id": CONTROLLER_ID,
                "name": "Internet 1",
                "purpose": "wan",
                "wan_failover_priority": 2,
                "wan_load_balance_type": "failover-only",
                "wan_networkgroup": "WAN",
            },
            {"name": "Bunker", "purpose": "corporate"},
        ]
    }


def udm_payload(
    *,
    wan2_alive: bool = True,
    wan_alive: bool = False,
    wan2_ip: str = PUBLIC_IP,
    speed: int = 10000,
    full_duplex: bool = True,
    devices: int = 1,
) -> object:
    device: dict[str, Any] = {
        "_id": CONTROLLER_ID,
        "type": "udm",
        "mac": WAN_MAC,
        "last_wan_ip": wan2_ip,
        "last_wan_interfaces": {
            "WAN": {"alive": wan_alive, "ip": "", "mac": WAN_MAC},
            "WAN2": {"alive": wan2_alive, "ip": wan2_ip, "mac": WAN_MAC},
        },
        "port_table": [
            {"port_idx": 9, "speed": 10, "full_duplex": False, "network_name": "wan"},
            {
                "port_idx": 10,
                "speed": speed,
                "full_duplex": full_duplex,
                "network_name": "wan2",
            },
        ],
    }
    return {"data": [device] * devices + [{"type": "uap", "mac": WAN_MAC}]}


def routing_payload(
    *,
    distance: int = 1,
    enabled: bool = True,
    copies: int = 1,
    network: str = "192.168.11.0/24",
) -> object:
    route: dict[str, Any] = {
        "_id": CONTROLLER_ID,
        "name": "WAS-110 LCT",
        "type": "static-route",
        "enabled": enabled,
        "static-route_type": "interface-route",
        "static-route_network": network,
        "static-route_distance": distance,
        "static-route_interface": CONTROLLER_ID,
    }
    return {"data": [route] * copies + [{"name": "other", "type": "static-route"}]}


def full_api(**udm_kwargs: Any) -> FakeApi:
    return FakeApi(
        {
            "/rest/networkconf": wan_configs(),
            "/stat/device": udm_payload(**udm_kwargs),
            "/rest/routing": routing_payload(),
        }
    )


def json_response(payload: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


def responder(response: httpx.Response) -> Callable[[str], httpx.Response]:
    def fetch(_: str) -> httpx.Response:
        return response

    return fetch


def constant_handler(
    response: httpx.Response,
) -> Callable[[httpx.Request], httpx.Response]:
    def handle(_: httpx.Request) -> httpx.Response:
        return response

    return handle


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def transport(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_login_succeeds_and_keeps_the_session_cookie() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert b"rememberMe" in request.content
        return httpx.Response(200, headers={"set-cookie": "TOKEN=abc; Path=/"})

    with transport(handler) as client:
        detail = MODULE.login(client, "https://10.10.20.1", "admin", PASSWORD)
    assert detail == "authenticated to controller"
    assert PASSWORD not in detail


def test_login_rejection_does_not_echo_the_password() -> None:
    handler = constant_handler(httpx.Response(401, json={"password": PASSWORD}))
    with transport(handler) as client, pytest.raises(SmokeFailure) as failure:
        _ = MODULE.login(client, "https://10.10.20.1", "admin", PASSWORD)
    assert "401" in str(failure.value)
    assert PASSWORD not in str(failure.value)


def test_login_without_a_cookie_fails() -> None:
    handler = constant_handler(httpx.Response(200, json={"meta": {"rc": "ok"}}))
    with (
        transport(handler) as client,
        pytest.raises(SmokeFailure, match="no session cookie"),
    ):
        _ = MODULE.login(client, "https://10.10.20.1", "admin", PASSWORD)


# ---------------------------------------------------------------------------
# WAN state
# ---------------------------------------------------------------------------


def test_wan_state_passes_with_was110_primary_and_empty_backup() -> None:
    api = full_api()
    detail = MODULE.check_wan_state(api, MODULE.UdmDevice(api))
    assert "WAS-110 primary on WAN2 alive" in detail
    assert "Internet 1 backup on WAN disconnected" in detail


def test_wan_state_fails_when_the_was110_path_is_down() -> None:
    api = full_api(wan2_alive=False)
    with pytest.raises(SmokeFailure, match=r"WAS-110 path .WAN2. is not alive"):
        _ = MODULE.check_wan_state(api, MODULE.UdmDevice(api))


def test_wan_state_fails_when_the_supplied_gateway_is_live() -> None:
    api = full_api(wan_alive=True)
    with pytest.raises(SmokeFailure, match="should be disconnected"):
        _ = MODULE.check_wan_state(api, MODULE.UdmDevice(api))


def test_ambiguous_wan_names_fail() -> None:
    duplicated = {
        "data": [
            {
                "name": "WAS-110",
                "purpose": "wan",
                "enabled": True,
                "wan_failover_priority": 1,
                "wan_load_balance_type": "weighted",
                "wan_networkgroup": "WAN2",
            }
        ]
        * 2
    }
    api = FakeApi({"/rest/networkconf": duplicated, "/stat/device": udm_payload()})
    with pytest.raises(SmokeFailure, match="expected exactly 1 match, found 2"):
        _ = MODULE.check_wan_state(api, MODULE.UdmDevice(api))


def test_missing_failover_priority_fails() -> None:
    payload: Any = wan_configs()
    del payload["data"][0]["wan_failover_priority"]
    api = FakeApi({"/rest/networkconf": payload, "/stat/device": udm_payload()})
    with pytest.raises(SmokeFailure, match="not an integer"):
        _ = MODULE.check_wan_state(api, MODULE.UdmDevice(api))


def test_networkconf_without_a_data_array_fails() -> None:
    api = FakeApi({"/rest/networkconf": {"meta": {"rc": "ok"}}})
    with pytest.raises(SmokeFailure, match="no 'data' field"):
        _ = MODULE.check_wan_state(api, MODULE.UdmDevice(api))


def test_networkconf_html_error_page_fails() -> None:
    api = FakeApi({"/rest/networkconf": "<html>login</html>"})
    with pytest.raises(SmokeFailure, match="expected a JSON object"):
        _ = MODULE.check_wan_state(api, MODULE.UdmDevice(api))


def test_two_udm_devices_fail() -> None:
    api = full_api(devices=2)
    with pytest.raises(SmokeFailure, match="udm device: expected exactly 1"):
        _ = MODULE.check_wan_state(api, MODULE.UdmDevice(api))


# ---------------------------------------------------------------------------
# WAN address
# ---------------------------------------------------------------------------


def test_public_wan_address_passes_without_printing_it() -> None:
    detail = MODULE.check_wan_public_ip(MODULE.UdmDevice(full_api()))
    assert detail == "WAN2 holds a public, non-CGNAT IPv4 address"
    assert PUBLIC_IP not in detail


@pytest.mark.parametrize(
    ("address", "reason"),
    [
        ("100.72.14.8", "CGNAT"),
        ("192.168.1.42", "not publicly routable"),
        ("10.10.20.1", "not publicly routable"),
        ("127.0.0.1", "not publicly routable"),
        ("169.254.5.5", "not publicly routable"),
        ("2606:4700:4700::1111", "not IPv4"),
        ("not-an-ip", "not a valid IP address"),
    ],
)
def test_unroutable_wan_addresses_fail_without_leaking_them(
    address: str, reason: str
) -> None:
    device = MODULE.UdmDevice(full_api(wan2_ip=address))
    with pytest.raises(SmokeFailure) as failure:
        _ = MODULE.check_wan_public_ip(device)
    assert reason in str(failure.value)
    assert address not in str(failure.value)


def test_missing_wan_address_fails() -> None:
    api = full_api(wan2_ip="")
    with pytest.raises(SmokeFailure, match="not a non-empty string"):
        _ = MODULE.check_wan_public_ip(MODULE.UdmDevice(api))


# ---------------------------------------------------------------------------
# UDM port 10
# ---------------------------------------------------------------------------


def test_port_ten_at_ten_gig_full_duplex_passes() -> None:
    detail = MODULE.check_udm_port(MODULE.UdmDevice(full_api()))
    assert detail == "port 10 negotiated 10000 Mbps full duplex"


def test_port_ten_link_downshift_fails() -> None:
    device = MODULE.UdmDevice(full_api(speed=1000))
    with pytest.raises(SmokeFailure, match="expected 10000, observed 1000"):
        _ = MODULE.check_udm_port(device)


def test_port_ten_half_duplex_fails() -> None:
    device = MODULE.UdmDevice(full_api(full_duplex=False))
    with pytest.raises(SmokeFailure, match="full duplex: expected True"):
        _ = MODULE.check_udm_port(device)


def test_port_table_without_port_ten_fails() -> None:
    payload: Any = udm_payload()
    payload["data"][0]["port_table"] = [{"port_idx": 9, "speed": 10}]
    api = FakeApi({"/stat/device": payload})
    with pytest.raises(SmokeFailure, match="udm port 10: expected exactly 1"):
        _ = MODULE.check_udm_port(MODULE.UdmDevice(api))


def test_port_table_of_the_wrong_shape_fails() -> None:
    payload: Any = udm_payload()
    payload["data"][0]["port_table"] = {"port_idx": 10}
    api = FakeApi({"/stat/device": payload})
    with pytest.raises(SmokeFailure, match="expected a JSON array"):
        _ = MODULE.check_udm_port(MODULE.UdmDevice(api))


# ---------------------------------------------------------------------------
# LCT route and reachability
# ---------------------------------------------------------------------------


def test_lct_route_passes_without_naming_the_interface_id() -> None:
    detail = MODULE.check_lct_route(FakeApi({"/rest/routing": routing_payload()}))
    assert detail == "one enabled interface route to 192.168.11.0/24 at distance 1"
    assert CONTROLLER_ID not in detail


def test_duplicate_lct_routes_fail() -> None:
    api = FakeApi({"/rest/routing": routing_payload(copies=2)})
    with pytest.raises(
        SmokeFailure, match="route named WAS-110 LCT: expected exactly 1"
    ):
        _ = MODULE.check_lct_route(api)


def test_disabled_lct_route_fails() -> None:
    api = FakeApi({"/rest/routing": routing_payload(enabled=False)})
    with pytest.raises(SmokeFailure, match="enabled: expected True"):
        _ = MODULE.check_lct_route(api)


def test_lct_route_redacts_an_unexpected_network() -> None:
    observed = "route-network-sentinel"
    api = FakeApi({"/rest/routing": routing_payload(network=observed)})
    with pytest.raises(SmokeFailure, match="does not match") as failure:
        _ = MODULE.check_lct_route(api)
    assert observed not in str(failure.value)


def test_lct_route_at_the_wrong_distance_fails() -> None:
    api = FakeApi({"/rest/routing": routing_payload(distance=5)})
    with pytest.raises(SmokeFailure, match="distance: expected 1, observed 5"):
        _ = MODULE.check_lct_route(api)


def test_lct_https_requires_a_successful_response() -> None:
    with pytest.raises(SmokeFailure, match="answered HTTP 401"):
        _ = MODULE.check_lct_https(responder(httpx.Response(401)))


def test_lct_https_timeout_fails() -> None:
    def timeout(_: str) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    with pytest.raises(SmokeFailure, match=r"unreachable .ConnectTimeout."):
        _ = MODULE.check_lct_https(timeout)


# ---------------------------------------------------------------------------
# NextDNS
# ---------------------------------------------------------------------------


def nextdns_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": "ok",
        "protocol": "DOH",
        "profile": NEXTDNS_PROFILE,
        "client": PUBLIC_IP,
        "srcIP": PUBLIC_IP,
    }
    body.update(overrides)
    return body


def test_nextdns_pass_hides_the_profile_and_client_ip() -> None:
    detail = MODULE.check_nextdns(responder(json_response(nextdns_body())))
    assert detail == "resolving over DoH with a linked profile"
    assert NEXTDNS_PROFILE not in detail
    assert PUBLIC_IP not in detail


def test_nextdns_unconfigured_status_fails() -> None:
    response = json_response(nextdns_body(status="unconfigured", profile=""))
    with pytest.raises(SmokeFailure, match="nextdns status"):
        _ = MODULE.check_nextdns(responder(response))


def test_nextdns_plain_dns_fails() -> None:
    response = json_response(nextdns_body(protocol="UDP"))
    with pytest.raises(SmokeFailure, match="expected DoH"):
        _ = MODULE.check_nextdns(responder(response))


def test_nextdns_without_a_profile_fails() -> None:
    response = json_response(nextdns_body(profile=""))
    with pytest.raises(SmokeFailure, match="'profile' is missing"):
        _ = MODULE.check_nextdns(responder(response))


def test_nextdns_non_json_body_fails() -> None:
    response = httpx.Response(200, text="<html>captive portal</html>")
    with pytest.raises(SmokeFailure, match="was not JSON"):
        _ = MODULE.check_nextdns(responder(response))


def test_nextdns_follows_the_browser_diagnostic_without_printing_its_host() -> None:
    diagnostic_url = f"https://{NEXTDNS_PROFILE}.test.nextdns.io/"
    responses = {
        MODULE.NEXTDNS_TEST_URL: httpx.Response(
            200,
            text=f"<script>xhr.open('GET', '{diagnostic_url}', false);</script>",
        ),
        diagnostic_url: json_response(nextdns_body()),
    }

    detail = MODULE.check_nextdns(responses.__getitem__)

    assert detail == "resolving over DoH with a linked profile"
    assert NEXTDNS_PROFILE not in detail


def test_nextdns_rejects_an_http_error_before_parsing() -> None:
    response = httpx.Response(503, text="<html>unavailable</html>")
    with pytest.raises(SmokeFailure, match="answered HTTP 503"):
        _ = MODULE.check_nextdns(responder(response))


def test_nextdns_network_error_fails() -> None:
    def refused(_: str) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(SmokeFailure, match=r"unreachable .ConnectError."):
        _ = MODULE.check_nextdns(refused)


# ---------------------------------------------------------------------------
# mDNS discovery
# ---------------------------------------------------------------------------

AIRPLAY_OUTPUT = """Browsing for _airplay._tcp.local.
Timestamp     A/R    Flags  if Domain               Service Type         Instance Name
21:59:12.502  Add        3   1 local.               _airplay._tcp.       Thurstons-MacBook-Pro
21:59:12.502  Add        3  14 local.               _airplay._tcp.       Kitchen
"""
HAP_OUTPUT = """Browsing for _hap._tcp.local.
21:59:33.353  Add        2  14 local.               _hap._tcp.           HomePodSensor 500623
"""


def test_discovery_passes_when_every_service_shows_the_homepod() -> None:
    browsed: list[str] = []

    def browse(service: str) -> str:
        browsed.append(service)
        return HAP_OUTPUT if service == "_hap._tcp" else AIRPLAY_OUTPUT

    detail = MODULE.check_discovery(browse)
    assert browsed == ["_airplay._tcp", "_raop._tcp", "_hap._tcp"]
    assert detail.startswith("Kitchen HomePod visible on")


def test_discovery_rejects_the_wrong_source_network() -> None:
    browsed = False

    def browse(_: str) -> str:
        nonlocal browsed
        browsed = True
        return AIRPLAY_OUTPUT

    with pytest.raises(SmokeFailure, match="must run from the YoRHa network"):
        _ = MODULE.check_discovery(browse, lambda: "10.10.40.25")
    assert not browsed


def test_discovery_ignores_removed_instances() -> None:
    removed = AIRPLAY_OUTPUT + (
        "21:59:13.502  Rmv        3  14 local.               "
        "_airplay._tcp.       Kitchen\n"
    )

    def browse(service: str) -> str:
        return HAP_OUTPUT if service == "_hap._tcp" else removed

    with pytest.raises(SmokeFailure, match=r"_airplay\._tcp"):
        _ = MODULE.check_discovery(browse)


def test_discovery_names_the_services_that_are_silent() -> None:
    def browse(service: str) -> str:
        if service == "_hap._tcp":
            return HAP_OUTPUT
        return "" if service == "_raop._tcp" else AIRPLAY_OUTPUT

    with pytest.raises(SmokeFailure, match=r"not advertised on _raop._tcp"):
        _ = MODULE.check_discovery(browse)


def test_discovery_rejects_an_unrelated_homepod() -> None:
    def browse(service: str) -> str:
        if service == "_hap._tcp":
            return HAP_OUTPUT
        return AIRPLAY_OUTPUT.replace("Kitchen", "Study HomePod")

    with pytest.raises(
        SmokeFailure,
        match=r"not advertised on _airplay._tcp, _raop._tcp",
    ):
        _ = MODULE.check_discovery(browse)


def test_discovery_reports_a_missing_dns_sd_binary() -> None:
    def browse(_: str) -> str:
        raise FileNotFoundError("dns-sd")

    with pytest.raises(SmokeFailure, match=r"dns-sd failed for .* .FileNotFoundError."):
        _ = MODULE.check_discovery(browse)


def test_browse_terminates_a_long_running_process(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "DISCOVERY_TIMEOUT", 1.0)
    monkeypatch.setattr(
        MODULE, "DISCOVERY_COMMAND", ("/bin/sh", "-c", "echo Kitchen; sleep 30")
    )
    started = time.monotonic()
    output = MODULE.dns_sd_browse("_airplay._tcp")
    elapsed = time.monotonic() - started
    assert "Kitchen" in output
    assert elapsed < 10.0


# ---------------------------------------------------------------------------
# Redaction across reported output
# ---------------------------------------------------------------------------


def test_reported_output_never_carries_secrets(capsys: CaptureFixture[str]) -> None:
    api = full_api()
    device = MODULE.UdmDevice(api)
    broken = full_api(wan2_alive=False, wan2_ip="100.72.0.9", speed=1000)
    broken_device = MODULE.UdmDevice(broken)
    checks: list[tuple[str, Callable[[], str]]] = [
        ("wan failover state", lambda: MODULE.check_wan_state(api, device)),
        ("wan public ipv4", lambda: MODULE.check_wan_public_ip(device)),
        ("udm port 10 link", lambda: MODULE.check_udm_port(device)),
        ("was-110 lct route", lambda: MODULE.check_lct_route(api)),
        (
            "nextdns doh resolution",
            lambda: MODULE.check_nextdns(responder(json_response(nextdns_body()))),
        ),
        ("broken wan state", lambda: MODULE.check_wan_state(broken, broken_device)),
        ("broken wan ipv4", lambda: MODULE.check_wan_public_ip(broken_device)),
        ("broken port", lambda: MODULE.check_udm_port(broken_device)),
        (
            "broken nextdns",
            lambda: MODULE.check_nextdns(
                responder(json_response(nextdns_body(status="unconfigured")))
            ),
        ),
    ]
    results = [MODULE.run_check(name, check) for name, check in checks]
    for result in results:
        MODULE.report(result)

    captured = capsys.readouterr()
    printed = captured.out + captured.err
    assert [result.passed for result in results] == [True] * 5 + [False] * 4
    for secret in SECRETS:
        assert secret not in printed
        assert all(secret not in result.detail for result in results)


def test_environment_failure_names_the_variable_only(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TF_VAR_unifi_username", raising=False)
    monkeypatch.setenv("TF_VAR_unifi_password", PASSWORD)

    assert MODULE.main() == 1

    captured = capsys.readouterr()
    assert "TF_VAR_unifi_username is not set" in captured.err
    assert PASSWORD not in captured.err + captured.out


def test_api_url_defaults_to_the_admin_gateway(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("TF_VAR_unifi_api_url", raising=False)
    assert MODULE.DEFAULT_API_URL == "https://10.10.20.1"


def test_controller_url_rejects_secret_bearing_components() -> None:
    sentinels = (
        "https://user:password-sentinel@controller.local",
        "https://controller.local?token=token-sentinel",
        "https://controller.local/#fragment-sentinel",
        "https://controller.local/api/secret-sentinel",
    )
    for value in sentinels:
        with pytest.raises(SmokeFailure) as failure:
            _ = MODULE.controller_base_url(value)
        assert not any(sentinel in str(failure.value) for sentinel in SECRETS)
        assert value not in str(failure.value)


def test_controller_url_accepts_an_https_origin() -> None:
    assert MODULE.controller_base_url("https://controller.local/") == (
        "https://controller.local"
    )
