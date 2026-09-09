import importlib.util
from pathlib import Path
import sys
from typing import Any, Never

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "bootstrap/targets/pod042/incus/reconcile.py"
SPEC = importlib.util.spec_from_file_location("pod042_incus", MODULE)
assert SPEC is not None and SPEC.loader is not None
incus: Any = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = incus
SPEC.loader.exec_module(incus)


def test_exact_storage_and_network_contract() -> None:
    assert incus.POOL_NAME == "black-box"
    assert incus.POOL == {
        "driver": "dir",
        "source": "/mnt/black-box/incus",
    }
    assert incus.NETWORK == {"type": "macvlan", "parent": "enp5s0", "vlan": "40"}


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
