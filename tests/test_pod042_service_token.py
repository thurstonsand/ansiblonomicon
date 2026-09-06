from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import stat
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
for name in ("fnox_host", "pod042_reconcile", "pod042_service_token"):
    spec = spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
service_token: Any = sys.modules["pod042_service_token"]


@pytest.mark.parametrize("value", ["", " \n", "one\ntwo", "one\rtwo", "x" * 65537])
def test_rejects_incomplete_or_multiple_token_records(value: str) -> None:
    with pytest.raises(service_token.ServiceTokenError, match="record"):
        service_token.token_record(value)


def test_token_convergence_and_rotation(tmp_path: Path) -> None:
    uid, gid = os.getuid(), os.getgid()
    assert service_token.converge_token(tmp_path, "first", uid, gid)
    token = tmp_path / ".config/op-service-account/token"
    metadata = token.stat()
    assert stat.S_IMODE(metadata.st_mode) == 0o600
    assert metadata.st_uid == uid
    assert stat.S_IMODE(token.parent.stat().st_mode) == 0o700
    assert token.read_text() == "first\n"
    assert not service_token.converge_token(tmp_path, "first", uid, gid)
    assert token.stat().st_ino == metadata.st_ino
    assert service_token.converge_token(tmp_path, "second", uid, gid)
    assert token.read_text() == "second\n"
    assert list(token.parent.iterdir()) == [token]


def test_permission_drift_is_repaired(tmp_path: Path) -> None:
    uid, gid = os.getuid(), os.getgid()
    service_token.converge_token(tmp_path, "first", uid, gid)
    token = tmp_path / ".config/op-service-account/token"
    token.chmod(0o644)
    token.parent.chmod(0o755)
    assert service_token.converge_token(tmp_path, "first", uid, gid)
    assert stat.S_IMODE(token.stat().st_mode) == 0o600
    assert stat.S_IMODE(token.parent.stat().st_mode) == 0o700


@pytest.mark.parametrize(
    "component",
    [".config", ".config/op-service-account", ".config/op-service-account/token"],
)
def test_refuses_symlinks_at_every_managed_component(
    tmp_path: Path, component: str
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    target = home / component
    target.parent.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    target.symlink_to(outside)
    with pytest.raises(OSError):
        service_token.converge_token(home, "sentinel", os.getuid(), os.getgid())
    assert not list(outside.iterdir())


@pytest.mark.parametrize("kind", ["directory", "fifo", "hardlink"])
def test_refuses_nonregular_or_shared_existing_token(tmp_path: Path, kind: str) -> None:
    token = tmp_path / ".config/op-service-account/token"
    token.parent.mkdir(parents=True)
    if kind == "directory":
        token.mkdir()
    elif kind == "fifo":
        os.mkfifo(token)
    else:
        token.write_text("old\n")
        os.link(token, tmp_path / "second-link")
    with pytest.raises(service_token.ServiceTokenError):
        service_token.converge_token(tmp_path, "sentinel", os.getuid(), os.getgid())


def test_stale_candidates_are_removed_on_noop_rerun(tmp_path: Path) -> None:
    uid, gid = os.getuid(), os.getgid()
    service_token.converge_token(tmp_path, "first", uid, gid)
    token = tmp_path / ".config/op-service-account/token"
    (token.parent / ".token-interrupted").write_text("old candidate")
    assert service_token.converge_token(tmp_path, "first", uid, gid)
    assert list(token.parent.iterdir()) == [token]
    assert service_token.fnox_host.read_token(token, uid) == "first"


def test_directory_only_drift_is_reported(tmp_path: Path) -> None:
    uid, gid = os.getuid(), os.getgid()
    service_token.converge_token(tmp_path, "first", uid, gid)
    (tmp_path / ".config/op-service-account").chmod(0o755)
    assert service_token.converge_token(tmp_path, "first", uid, gid)
    assert not service_token.converge_token(tmp_path, "first", uid, gid)


def test_non_utf8_existing_token_is_replaced_without_decoding(tmp_path: Path) -> None:
    uid, gid = os.getuid(), os.getgid()
    service_token.converge_token(tmp_path, "first", uid, gid)
    token = tmp_path / ".config/op-service-account/token"
    token.write_bytes(b"\xff\xfe")
    assert service_token.converge_token(tmp_path, "replacement", uid, gid)
    assert service_token.fnox_host.read_token(token, uid) == "replacement"
