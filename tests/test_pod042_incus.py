import importlib.util
from pathlib import Path
import subprocess
import sys
import tomllib
from typing import Any, Never

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "bootstrap/targets/pod042/incus/reconcile.py"
SPEC = importlib.util.spec_from_file_location("pod042_incus", MODULE)
assert SPEC is not None and SPEC.loader is not None
incus: Any = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = incus
SPEC.loader.exec_module(incus)


def test_exact_haos_vm_and_network_contract() -> None:
    assert incus.IMAGE_VERSION == "18.2"
    assert incus.IMAGE_URL.endswith("/18.2/haos_ova-18.2.qcow2.xz")
    assert incus.IMAGE_SHA256 == (
        "254e53f354df0739e3afc09be5431a07df53f0df6b703885404f665c454f254e"
    )
    assert incus.POOL == {
        "driver": "dir",
        "source": "/mnt/black-box/agents/incus",
    }
    assert incus.NETWORK == {"type": "macvlan", "parent": "enp5s0", "vlan": "40"}
    assert incus.VM_CONFIG == {
        "limits.cpu": "4",
        "limits.memory": "8GiB",
        "security.secureboot": "false",
        "security.csm": "false",
        "boot.autostart": "true",
    }
    assert incus.MAC == "00:16:3e:48:41:42"


def test_check_missing_vm_never_downloads_or_mutates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def record_access(apply: bool) -> None:
        calls.append(("access", str(apply)))

    def read_resource(kind: str, _name: str) -> dict[str, Any] | None:
        if kind == "config":
            return None
        if kind == "storage":
            return {"driver": "dir", "config": {"source": incus.POOL["source"]}}
        return {
            "type": "macvlan",
            "managed": True,
            "config": {"parent": "enp5s0", "vlan": "40"},
        }

    def record_run(*args: str, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    def fail_download(*_args: object, **_kwargs: object) -> Never:
        pytest.fail("check downloaded seed")

    monkeypatch.setattr(incus, "verify_host", lambda: None)
    monkeypatch.setattr(incus.os, "geteuid", lambda: 0)
    monkeypatch.setattr(incus, "ensure_access", record_access)
    monkeypatch.setattr(incus, "incus_json", read_resource)
    monkeypatch.setattr(incus, "run", record_run)
    monkeypatch.setattr(incus, "urlopen", fail_download)

    with pytest.raises(ValueError, match="instance is missing"):
        incus.reconcile("check")

    assert calls == [("access", "False")]


@pytest.mark.parametrize(
    ("kind", "value", "message"),
    [
        (
            "storage",
            {"driver": "zfs", "config": {"source": "black-box/incus"}},
            "incompatible identity",
        ),
        (
            "network",
            {"type": "bridge", "config": {"parent": "enp5s0", "vlan": "40"}},
            "incompatible identity",
        ),
    ],
)
def test_incompatible_owned_resource_fails_without_mutation(
    monkeypatch: pytest.MonkeyPatch, kind: str, value: dict[str, object], message: str
) -> None:
    def read_resource(requested: str, _name: str) -> dict[str, object] | None:
        return value if requested == kind else None

    def fail_run(*_args: str, **_kwargs: object) -> Never:
        pytest.fail("mismatch was mutated")

    monkeypatch.setattr(incus, "incus_json", read_resource)
    monkeypatch.setattr(incus, "run", fail_run)
    with pytest.raises(ValueError, match=message):
        (incus.ensure_pool if kind == "storage" else incus.ensure_network)(True)


@pytest.mark.parametrize("status, memory", [("Stopped", "8GiB"), ("Running", "4GiB")])
def test_check_fails_for_stopped_or_misconfigured_vm(
    monkeypatch: pytest.MonkeyPatch, status: str, memory: str
) -> None:
    config = {
        **incus.VM_CONFIG,
        "limits.memory": memory,
    }
    instance = {
        "type": "virtual-machine",
        "architecture": "x86_64",
        "config": config,
        "devices": {
            "root": {"pool": "local", "type": "disk", "path": "/", "size": "64GiB"},
            "eth0": {
                "type": "nic",
                "network": "scanners",
                "hwaddr": incus.MAC,
                "name": "eth0",
            },
        },
    }

    def read_instance(kind: str, _name: str) -> dict[str, Any]:
        return {"status": status} if kind == "info" else instance

    def fail_run(*_args: str, **_kwargs: object) -> Never:
        pytest.fail("check mutated VM")

    monkeypatch.setattr(incus, "incus_json", read_instance)
    monkeypatch.setattr(incus, "run", fail_run)

    with pytest.raises(ValueError, match="differs from its declaration"):
        incus.ensure_vm(False)


def test_native_declaration_owns_only_incus_package_and_ordinary_directory() -> None:
    declaration = tomllib.loads(
        (ROOT / "bootstrap/targets/pod042/mise.incus.toml").read_text()
    )["bootstrap"]
    assert declaration["packages"] == {"apt:incus": "latest"}
    assert declaration["directories"]["/mnt/black-box/agents/incus"] == {
        "owner": "root",
        "group": "root",
        "mode": "0711",
    }
    layout = (ROOT / "bootstrap/targets/pod042/datasets/layout.toml").read_text()
    assert "black-box/agents/incus" not in layout


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
