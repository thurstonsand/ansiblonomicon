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


def test_exact_haos_vm_contract() -> None:
    assert home_assistant.IMAGE_VERSION == "18.2"
    assert home_assistant.IMAGE_URL.endswith("/18.2/haos_ova-18.2.qcow2.xz")
    assert home_assistant.IMAGE_SHA256 == (
        "254e53f354df0739e3afc09be5431a07df53f0df6b703885404f665c454f254e"
    )
    assert home_assistant.VM_CONFIG == {
        "limits.cpu": "4",
        "limits.memory": "8GiB",
        "security.secureboot": "false",
        "security.csm": "false",
        "boot.autostart": "true",
    }
    assert home_assistant.MAC == "00:16:3e:48:41:42"


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
    instance = {
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
        },
    }

    def read_instance(kind: str, _name: str) -> dict[str, Any]:
        return {"status": status} if kind == "info" else instance

    def fail_run(*_args: str, **_kwargs: object) -> Never:
        pytest.fail("check mutated VM")

    monkeypatch.setattr(home_assistant.incus, "incus_json", read_instance)
    monkeypatch.setattr(home_assistant.incus, "run", fail_run)

    with pytest.raises(ValueError, match="differs from its declaration"):
        home_assistant.ensure_vm(False)


def test_unifi_home_assistant_contract() -> None:
    ports = (ROOT / "terraform/unifi/ports.tf").read_text()
    clients = (ROOT / "terraform/unifi/clients.tf").read_text()
    profile = ports.split('resource "unifi_port_profile" "pod042"', 1)[1].split(
        "}\n", 1
    )[0]
    assert "native_networkconf_id" in profile and "unifi_network.bunker.id" in profile
    assert "tagged_networkconf_ids" not in profile
    assert "unifi_network.scanners.id" not in profile
    for network in ("yorha", "lunar_tear", "the_village"):
        assert f"unifi_network.{network}.id" in profile
    assert "tagged_vlan_mgmt" in profile and '"custom"' in profile
    port = ports.split("index           = 17", 1)[1].split("}", 1)[0]
    assert "unifi_port_profile.pod042.id" in port
    assert 'mac              = "00:16:3e:48:41:42"' in clients
    assert 'fixed_ip         = "10.10.40.42"' in clients
    assert 'local_dns_record = "home-assistant"' in clients
