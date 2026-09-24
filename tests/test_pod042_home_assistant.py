import importlib.util
from pathlib import Path
import subprocess
import sys
from typing import Any, Never

import pytest

ROOT = Path(__file__).resolve().parents[1]
INCUS_DIR = ROOT / "bootstrap/targets/pod042/incus"
sys.path.insert(0, str(INCUS_DIR))
MODULE = INCUS_DIR / "home_assistant.py"
SPEC = importlib.util.spec_from_file_location("pod042_home_assistant", MODULE)
assert SPEC is not None and SPEC.loader is not None
home_assistant: Any = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = home_assistant
SPEC.loader.exec_module(home_assistant)


def declared_instance(config: dict[str, str]) -> dict[str, Any]:
    return {
        "type": "virtual-machine",
        "architecture": "x86_64",
        "config": config,
        "devices": {
            "root": {
                "pool": home_assistant.incus.POOL_NAME,
                "type": "disk",
                "path": "/",
                "size": "64GiB",
            },
            "eth0": {
                "type": "nic",
                "network": "scanners",
                "hwaddr": home_assistant.MAC,
                "name": "eth0",
            },
            "zbt-2": home_assistant.ZBT_2,
            "bluetooth": home_assistant.BLUETOOTH,
        },
    }


def test_check_missing_vm_never_downloads_or_mutates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def record_run(*args: str, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    def fail_download(*_args: object, **_kwargs: object) -> Never:
        pytest.fail("check downloaded seed")

    def missing_resource(_kind: str, _name: str) -> dict[str, Any] | None:
        return None

    monkeypatch.setattr(home_assistant.incus, "verify_host", lambda: None)
    monkeypatch.setattr(home_assistant.os, "geteuid", lambda: 0)
    monkeypatch.setattr(home_assistant.incus, "incus_json", missing_resource)
    monkeypatch.setattr(home_assistant.incus, "run", record_run)
    monkeypatch.setattr(home_assistant, "urlopen", fail_download)

    with pytest.raises(ValueError, match="instance is missing"):
        home_assistant.reconcile("check")

    assert calls == []


@pytest.mark.parametrize("status, memory", [("Stopped", "8GiB"), ("Running", "4GiB")])
def test_check_fails_for_stopped_or_misconfigured_vm(
    monkeypatch: pytest.MonkeyPatch, status: str, memory: str
) -> None:
    config = {
        **home_assistant.VM_CONFIG,
        "limits.memory": memory,
    }
    instance = declared_instance(config)

    def read_instance(kind: str, _name: str) -> dict[str, Any]:
        return {"status": status} if kind == "info" else instance

    def fail_run(*_args: str, **_kwargs: object) -> Never:
        pytest.fail("check mutated VM")

    monkeypatch.setattr(home_assistant.incus, "incus_json", read_instance)
    monkeypatch.setattr(home_assistant.incus, "run", fail_run)

    with pytest.raises(ValueError, match="differs from its declaration"):
        home_assistant.ensure_vm(False)


def test_apply_hotplugs_zbt_2_into_running_vm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = declared_instance(home_assistant.VM_CONFIG)
    del instance["devices"]["zbt-2"]
    calls: list[tuple[str, ...]] = []

    def read_instance(kind: str, _name: str) -> dict[str, Any]:
        return {"status": "Running"} if kind == "info" else instance

    def record_run(*args: str, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(home_assistant.incus, "incus_json", read_instance)
    monkeypatch.setattr(home_assistant.incus, "run", record_run)

    home_assistant.ensure_vm(True)

    assert calls == [
        (
            "/usr/bin/incus",
            "config",
            "device",
            "add",
            "home-assistant",
            "zbt-2",
            "usb",
            "vendorid=303a",
            "productid=831a",
            "serial=1CDBD45E7B24",
        )
    ]
