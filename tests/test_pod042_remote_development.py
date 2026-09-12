import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "pod042_remote_development",
    ROOT / "bootstrap/targets/pod042/remote-development/services.py",
)
assert spec is not None and spec.loader is not None
services = importlib.util.module_from_spec(spec)
spec.loader.exec_module(services)


@pytest.mark.parametrize("missing", ["desired", "authenticated"])
def test_requires_enrollment(monkeypatch: pytest.MonkeyPatch, missing: str):
    state = {"desired": True, "authenticated": True, "linked": False}
    state[missing] = False

    def output(*args: str) -> str:
        return json.dumps(state)

    monkeypatch.setattr(services, "output", output)
    with pytest.raises(SystemExit, match="enrollment missing"):
        services.require_t3()


def apply_services(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    herdr_running: bool = False,
    herdr_binary_stale: bool = False,
    herdr_unit_active: bool = False,
) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []

    def output(*command: str) -> str:
        if command[1:4] == ("connect", "status", "--json"):
            return json.dumps({"desired": True, "authenticated": True, "linked": False})
        if command[1:4] == ("status", "server", "--json"):
            return json.dumps(
                {"running": herdr_running, "server_binary_stale": herdr_binary_stale}
            )
        if command[0] == "loginctl":
            return "yes"
        if command[0] == "systemctl":
            return "no"
        raise AssertionError(command)

    def run(*command: str) -> None:
        calls.append(command)

    def user(uid: int) -> SimpleNamespace:
        return SimpleNamespace(pw_name="thurstonsand")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(services, "HOME", tmp_path)
    monkeypatch.setattr(services.os, "environ", {})
    monkeypatch.setattr(services, "output", output)
    monkeypatch.setattr(services, "run", run)
    monkeypatch.setattr(services, "require_amp", lambda: None)

    def unit_active(unit: str) -> bool:
        return herdr_unit_active

    monkeypatch.setattr(services, "unit_active", unit_active)
    monkeypatch.setattr(services.socket, "gethostname", lambda: "pod042")
    monkeypatch.setattr(services.os, "getuid", lambda: 1000)
    monkeypatch.setattr(services.pwd, "getpwuid", user)
    monkeypatch.setattr("sys.argv", ["services.py", "apply"])
    services.main()
    return calls


def test_starts_enrolled_service_before_first_link(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    calls = apply_services(monkeypatch, tmp_path)
    assert ("systemctl", "--user", "start", "t3code.service") in calls
    assert ("systemctl", "--user", "start", "amp-remote.service") in calls
    assert ("systemctl", "--user", "enable", "herdr.service") in calls
    assert ("systemctl", "--user", "start", "herdr.service") in calls


def test_leaves_an_unowned_herdr_server_alone_when_none_is_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    calls = apply_services(monkeypatch, tmp_path)
    assert not [call for call in calls if call[1:] == ("server", "stop")]


def test_stops_a_herdr_server_systemd_does_not_own(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    calls = apply_services(monkeypatch, tmp_path, herdr_running=True)
    stop = [call for call in calls if call[1:] == ("server", "stop")]
    assert len(stop) == 1
    assert calls.index(stop[0]) < calls.index(
        ("systemctl", "--user", "enable", "herdr.service")
    )


def test_keeps_a_herdr_server_systemd_already_owns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    calls = apply_services(
        monkeypatch, tmp_path, herdr_running=True, herdr_unit_active=True
    )
    assert not [call for call in calls if call[1:] == ("server", "stop")]


def test_restarts_herdr_when_its_binary_is_stale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    calls = apply_services(
        monkeypatch, tmp_path, herdr_unit_active=True, herdr_binary_stale=True
    )
    assert ("systemctl", "--user", "restart", "herdr.service") in calls
    assert ("systemctl", "--user", "start", "herdr.service") not in calls
