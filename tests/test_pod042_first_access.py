from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/pod042_first_access.py"
SPEC = spec_from_file_location("pod042_first_access", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
pod042_first_access: Any = module_from_spec(SPEC)
sys.modules[SPEC.name] = pod042_first_access
SPEC.loader.exec_module(pod042_first_access)


def login_item(item_id: str | None = None) -> dict[str, object]:
    item: dict[str, object] = {
        "title": "Login",
        "fields": [
            {"id": "username", "value": ""},
            {"id": "password", "value": ""},
        ],
    }
    if item_id is not None:
        item["id"] = item_id
    return item


def test_store_password_uses_json_stdin_not_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], str | None]] = []
    monkeypatch.setattr(
        pod042_first_access, "password_item", lambda: (login_item(), False)
    )

    def record_command(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        input_text = kwargs.get("input_text")
        assert input_text is None or isinstance(input_text, str)
        calls.append((argv, input_text))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(pod042_first_access, "command", record_command)

    pod042_first_access.store_password("sentinel-secret")

    argv, payload = calls[0]
    assert "sentinel-secret" not in " ".join(argv)
    assert payload is not None
    parsed = json.loads(payload)
    values = {field["id"]: field["value"] for field in parsed["fields"]}
    assert values == {"username": "thurstonsand", "password": "sentinel-secret"}


def test_existing_password_item_is_edited_by_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        pod042_first_access,
        "password_item",
        lambda: (login_item("existing-item"), True),
    )

    def record_command(
        argv: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(pod042_first_access, "command", record_command)

    pod042_first_access.store_password("sentinel-secret")

    assert calls[0][:4] == ["op", "item", "edit", "existing-item"]
    assert "sentinel-secret" not in " ".join(calls[0])


def test_password_bridge_never_places_password_in_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def record_command(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(pod042_first_access, "command", record_command)

    pod042_first_access.install_key("10.10.10.99", "sentinel-secret")
    pod042_first_access.establish_passwordless_sudo("10.10.10.99", "sentinel-secret")

    assert all("sentinel-secret" not in " ".join(argv) for argv, _kwargs in calls)
    assert calls[0][1]["env"]["SSHPASS"] == "sentinel-secret"  # type: ignore[index]
    assert calls[1][1]["input_text"] == "sentinel-secret\n"


def test_login_template_requires_built_in_fields() -> None:
    with pytest.raises(pod042_first_access.FirstAccessError, match="lacks fields"):
        pod042_first_access.replace_login_fields({"fields": []}, "password")
