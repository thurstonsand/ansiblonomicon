from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
for name in ("automation_identity", "pod042_first_access"):
    spec = spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
pod042_first_access: Any = sys.modules["pod042_first_access"]


@pytest.fixture
def fake_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    def read_identity(_path: Path, _owner: int) -> str:
        return "synthetic-token"

    monkeypatch.setattr(pod042_first_access, "read_identity", read_identity)


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
    fake_identity: None,
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
    fake_identity: None,
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


def test_op_authority_is_validated_and_child_scoped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "stale-token")
    monkeypatch.setenv("OP_SESSION_personal", "desktop-session")
    monkeypatch.setenv("OP_CONNECT_TOKEN", "connect-token")
    monkeypatch.setenv("FNOX_HOST_OP_TOKEN", "other-token")
    inherited = dict(os.environ)
    reads: list[tuple[Path, int]] = []

    def read_identity(path: Path, owner: int) -> str:
        reads.append((path, owner))
        return "synthetic-token"

    def record_command(
        argv: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        assert argv == ["op", "item", "list", "--vault", "agent", "--format=json"]
        environment = kwargs["env"]
        assert {
            key: value
            for key, value in environment.items()
            if key.startswith(("OP_", "FNOX_"))
        } == {"OP_SERVICE_ACCOUNT_TOKEN": "synthetic-token"}
        assert "synthetic-token" not in " ".join(argv)
        assert kwargs["capture_output"] is True
        return subprocess.CompletedProcess(argv, 0, "[]", "")

    monkeypatch.setattr(pod042_first_access, "read_identity", read_identity)
    monkeypatch.setattr(pod042_first_access, "command", record_command)
    pod042_first_access.op_command(
        ["item", "list", "--vault", "agent", "--format=json"]
    )
    assert reads == [(tmp_path / ".config/fnox/config.toml", os.getuid())]
    assert dict(os.environ) == inherited


@pytest.mark.parametrize("missing", [True, False])
def test_invalid_identity_never_falls_back_to_desktop(
    monkeypatch: pytest.MonkeyPatch, missing: bool
) -> None:
    def read_identity(path: Path, owner: int) -> str:
        if missing:
            raise FileNotFoundError(path)
        raise pod042_first_access.IdentityError("unsafe identity permissions")

    def unexpected_command(*args: object, **kwargs: object) -> None:
        pytest.fail("op must not run without the validated identity")

    monkeypatch.setattr(pod042_first_access, "read_identity", read_identity)
    monkeypatch.setattr(pod042_first_access, "command", unexpected_command)
    error = (
        pod042_first_access.FirstAccessError
        if missing
        else pod042_first_access.IdentityError
    )
    with pytest.raises(error, match=r"enroll|unsafe identity"):
        pod042_first_access.op_command(["item", "list"])


@pytest.mark.parametrize("existing", [True, False])
def test_password_item_lists_exact_title_before_get_or_template(
    monkeypatch: pytest.MonkeyPatch, fake_identity: None, existing: bool
) -> None:
    calls: list[list[str]] = []
    metadata = [{"id": "other", "title": "pod042-old"}]
    if existing:
        metadata.append({"id": "matching-id", "title": "pod042"})

    def record_command(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        assert kwargs.get("check", True) is True
        payload = metadata if len(calls) == 1 else login_item("matching-id")
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

    monkeypatch.setattr(pod042_first_access, "command", record_command)
    item, exists = pod042_first_access.password_item()
    assert exists is existing
    assert item["id"] == "matching-id"
    assert calls[0] == ["op", "item", "list", "--vault", "agent", "--format=json"]
    assert calls[1] == (
        [
            "op",
            "item",
            "get",
            "matching-id",
            "--vault",
            "agent",
            "--format=json",
            "--reveal",
        ]
        if existing
        else ["op", "item", "template", "get", "Login"]
    )


def test_duplicate_exact_titles_fail_without_read_or_write(
    monkeypatch: pytest.MonkeyPatch, fake_identity: None
) -> None:
    calls: list[list[str]] = []

    def record_command(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(
            argv,
            0,
            json.dumps(
                [{"id": "one", "title": "pod042"}, {"id": "two", "title": "pod042"}]
            ),
            "",
        )

    monkeypatch.setattr(pod042_first_access, "command", record_command)
    with pytest.raises(pod042_first_access.FirstAccessError, match="multiple pod042"):
        pod042_first_access.store_password("synthetic-password")
    assert len(calls) == 1


@pytest.mark.parametrize("failure_at", ["list", "get", "edit", "template", "create"])
def test_op_failure_never_falls_back_to_creation(
    monkeypatch: pytest.MonkeyPatch, fake_identity: None, failure_at: str
) -> None:
    calls: list[list[str]] = []

    def record_command(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        assert kwargs.get("check", True) is True
        if argv[2] == failure_at:
            raise subprocess.CalledProcessError(
                23, argv, stderr="synthetic auth failure"
            )
        payload = (
            (
                []
                if failure_at in {"template", "create"}
                else [{"id": "existing", "title": "pod042"}]
            )
            if argv[2] == "list"
            else login_item("existing")
        )
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

    monkeypatch.setattr(pod042_first_access, "command", record_command)
    with pytest.raises(subprocess.CalledProcessError) as error:
        pod042_first_access.store_password("synthetic-password")
    assert error.value.returncode == 23
    assert calls[-1][2] == failure_at
    assert sum(argv[2] == "create" for argv in calls) == (failure_at == "create")
