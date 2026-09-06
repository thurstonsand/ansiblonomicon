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


def test_starts_enrolled_service_before_first_link(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    calls: list[tuple[str, ...]] = []

    def output(*command: str) -> str:
        if command[1:4] == ("connect", "status", "--json"):
            return json.dumps({"desired": True, "authenticated": True, "linked": False})
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
    monkeypatch.setattr(services.socket, "gethostname", lambda: "pod042")
    monkeypatch.setattr(services.os, "getuid", lambda: 1000)
    monkeypatch.setattr(services.pwd, "getpwuid", user)
    monkeypatch.setattr("sys.argv", ["services.py", "apply"])
    services.main()
    assert ("systemctl", "--user", "start", "t3code.service") in calls
    assert ("systemctl", "--user", "start", "amp-remote.service") in calls
