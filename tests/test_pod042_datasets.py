from collections.abc import Sequence
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1] / "bootstrap/targets/pod042"
spec = importlib.util.spec_from_file_location(
    "pod042_datasets", ROOT / "datasets/reconcile.py"
)
assert spec is not None and spec.loader is not None
policy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = policy
with patch.object(sys, "path", [str(ROOT / "maintenance"), *sys.path]):
    spec.loader.exec_module(policy)

ACTIVE = {
    "ark/media",
    "black-box/agents",
    "black-box/docker",
    "black-box/ghost-mysql",
    "black-box/incus",
}


def run_check(
    monkeypatch: pytest.MonkeyPatch,
    extra: Sequence[str] = (),
) -> dict[str, dict[str, str]]:
    existing = ACTIVE | {"ark", "black-box"} | set(extra)

    def output(*args: str) -> str:
        if args[0] == "/usr/sbin/zpool":
            return policy.POOLS[args[-1]]
        assert args[:3] == ("/usr/sbin/zfs", "list", "-H")
        return "\n".join(f"{name}\tfilesystem" for name in sorted(existing))

    def properties(name: str, keys: Sequence[str]) -> dict[str, object]:
        values = {
            policy.LAYOUT: "fresh-v1",
            policy.VERIFIED: "verified",
            "casesensitivity": (
                "insensitive" if name == "black-box/ghost-mysql" else "sensitive"
            ),
            "normalization": "none",
            "encryption": "off",
            "mounted": "yes" if name in ACTIVE else "no",
        }
        return {key: policy.Property(values[key], "local") for key in keys}

    changes: dict[str, dict[str, str]] = {}

    def converge(name: str, values: dict[str, str], apply: bool) -> None:
        changes[name] = values

    def group(name: str) -> SimpleNamespace:
        return SimpleNamespace(gr_gid=3000)

    def stat(path: Path) -> SimpleNamespace:
        return SimpleNamespace(st_uid=0, st_gid=3000, st_mode=0o2775)

    monkeypatch.setattr(policy.os, "geteuid", lambda: 0)
    monkeypatch.setattr(policy.grp, "getgrnam", group)
    monkeypatch.setattr(policy, "output", output)
    monkeypatch.setattr(policy, "properties", properties)
    monkeypatch.setattr(policy, "converge", converge)
    monkeypatch.setattr(policy.Path, "stat", stat)
    policy.reconcile(ROOT / "datasets/layout.toml", "check")
    return changes


def test_active_datasets_and_readonly_pool_roots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changes = run_check(monkeypatch)
    assert {
        name for name, props in changes.items() if props["readonly"] == "off"
    } == ACTIVE
    for name in ("ark", "black-box"):
        assert changes[name] == {
            "readonly": "on",
            "canmount": "off",
            "mountpoint": "none",
        }
    assert all(changes[name]["xattr"] == "on" for name in ACTIVE)


@pytest.mark.parametrize(
    "source", ["ark/anypod", "black-box/docker/anypod", "black-box/docker/plex"]
)
def test_old_active_names_require_explicit_cutover(
    monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    with pytest.raises(ValueError, match="Unclassified dataset"):
        run_check(monkeypatch, [source])


def test_retired_legacy_namespace_is_not_tolerated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="Unclassified dataset"):
        run_check(monkeypatch, ["black-box/legacy/old-vm"])
