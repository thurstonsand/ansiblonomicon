from collections.abc import Sequence
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import sys
import tomllib
from typing import Any
from unittest.mock import Mock

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/pod042_reconcile.py"
SPEC = spec_from_file_location("pod042_reconcile", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
pod042_reconcile: Any = module_from_spec(SPEC)
sys.modules[SPEC.name] = pod042_reconcile
SPEC.loader.exec_module(pod042_reconcile)


def completed(
    stdout: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


def test_target_declares_serial_native_landing_zone() -> None:
    target = tomllib.loads(
        (MODULE_PATH.parents[1] / "bootstrap/targets/pod042/mise.toml").read_text()
    )
    base = tomllib.loads(
        (MODULE_PATH.parents[1] / "bootstrap/targets/pod042/mise.base.toml").read_text()
    )
    storage = tomllib.loads(
        (
            MODULE_PATH.parents[1] / "bootstrap/targets/pod042/mise.storage.toml"
        ).read_text()
    )

    assert target["settings"]["jobs"] == 1
    assert target["settings"]["system_packages"]["managers"] == ["apt"]
    assert "bootstrap" not in target
    assert base["bootstrap"]["users"]["thurstonsand"]["groups"] == ["sudo"]
    assert base["bootstrap"]["users"]["thurstonsand"]["shell"] == "/usr/bin/zsh"
    assert base["bootstrap"]["packages"]["apt:zsh"] == "latest"
    assert (
        base["bootstrap"]["files"]["/etc/ssh/sshd_config.d/00-ansiblonomicon.conf"][
            "content"
        ]
        == "ClientAliveCountMax 3\n"
        "ClientAliveInterval 30\n"
        "PasswordAuthentication no\n"
        "PermitRootLogin no\n"
        "PrintLastLog yes\n"
        "PubkeyAuthentication yes\n"
    )
    assert storage["bootstrap"]["packages"]["apt:zfsutils-linux"] == "latest"
    assert storage["bootstrap"]["services"]["zfs-import-cache"]["enabled"] is True
    assert storage["bootstrap"]["services"]["zfs-mount"]["enabled"] is True


def test_capability_environments_are_explicit_and_disjoint() -> None:
    target_root = MODULE_PATH.parents[1] / "bootstrap/targets/pod042"
    environment_files = {
        path.stem.removeprefix("mise."): tomllib.loads(path.read_text())
        for path in target_root.glob("mise.*.toml")
    }
    assert set(environment_files) == set(pod042_reconcile.CAPABILITIES)

    exclusive_tables = (
        "packages",
        "groups",
        "users",
        "directories",
        "files",
        "services",
        "repos",
    )
    owners: dict[tuple[str, str], str] = {}
    for capability, config in environment_files.items():
        bootstrap = config.get("bootstrap", {})
        for table in exclusive_tables:
            for resource in bootstrap.get(table, {}):
                key = (table, resource)
                assert key not in owners, (
                    f"{table} resource {resource!r} belongs to both "
                    f"{owners[key]!r} and {capability!r}"
                )
                owners[key] = capability
        for task in config.get("tasks", {}):
            key = ("tasks", task)
            assert key not in owners, (
                f"task {task!r} belongs to both {owners[key]!r} and {capability!r}"
            )
            owners[key] = capability

    inventory = tomllib.loads(
        (MODULE_PATH.parents[1] / "bootstrap/mise.toml").read_text()
    )
    assert tuple(inventory["bootstrap"]["remote"]["hosts"]["pod042"]["mise_env"]) == (
        pod042_reconcile.CAPABILITIES
    )


def test_incus_capability_closure() -> None:
    assert pod042_reconcile.capabilities_for("incus") == (
        "network",
        "repositories",
        "storage",
        "datasets",
        "incus",
    )


def test_network_capability_includes_package_repositories() -> None:
    assert pod042_reconcile.capabilities_for("network") == (
        "repositories",
        "network",
    )


def test_home_assistant_capability_closure() -> None:
    assert pod042_reconcile.capabilities_for("home-assistant") == (
        "network",
        "repositories",
        "storage",
        "datasets",
        "incus",
        "home-assistant",
    )


def test_check_uses_native_bootstrap_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def accept_hostname() -> None:
        pass

    def record_command(
        argv: Sequence[str],
        *,
        check: bool = True,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        return completed()

    monkeypatch.setattr(pod042_reconcile, "assert_hostname", accept_hostname)
    monkeypatch.setattr(pod042_reconcile, "run_command", record_command)

    pod042_reconcile.run_local("base", check_mode=True)

    assert calls == [
        [
            "env",
            f"MISE_CEILING_PATHS={pod042_reconcile.TARGET_ROOT.parent}",
            f"MISE_TRUSTED_CONFIG_PATHS={pod042_reconcile.TARGET_ROOT}",
            "MISE_ENV=base",
            "mise",
            "-C",
            str(pod042_reconcile.TARGET_ROOT),
            "bootstrap",
            "plan",
        ],
        [
            "sudo",
            "-n",
            "/usr/bin/python3",
            str(pod042_reconcile.TARGET_ROOT / "base/check.py"),
        ],
    ]


@pytest.mark.parametrize(
    "capability", ["base", "operator", "agent-harness", "remote-development"]
)
def test_base_packages_precede_local_accounts(
    monkeypatch: pytest.MonkeyPatch, capability: str
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pod042_reconcile, "assert_hostname", Mock())
    monkeypatch.setattr(pod042_reconcile, "run_command", calls.append)

    pod042_reconcile.run_local(capability, check_mode=False)

    assert len(calls) == 2
    assert "MISE_ENV=base" in calls[0]
    assert calls[0][-4:] == ["bootstrap", "--only", "packages", "--yes"]
    assert calls[1][-2:] == ["bootstrap", "--yes"]
    assert "--only" not in calls[1]


def test_unknown_capability_fails_before_building_a_command() -> None:
    with pytest.raises(
        pod042_reconcile.ReconcileError, match="unknown pod042 capability"
    ):
        pod042_reconcile.capabilities_for("not-real")


def test_wrong_local_hostname_fails_before_reconcile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pod042_reconcile.socket, "gethostname", lambda: "not-pod042")
    monkeypatch.setattr(pod042_reconcile, "run_command", Mock())

    with pytest.raises(pod042_reconcile.ReconcileError, match="requires hostname"):
        pod042_reconcile.run([])


@pytest.mark.parametrize(
    "capability,expected",
    [
        ("alerting", {"HARK_WEBHOOK_URL_POD042"}),
        ("containers", set(pod042_reconcile.CONTAINER_SECRETS)),
        ("monitoring", {"HARK_WEBHOOK_URL_POD042", "HEALTHCHECKS_API_KEY"}),
        ("operator", set[str]()),
    ],
)
def test_local_capability_selects_only_consumed_secrets(
    monkeypatch: pytest.MonkeyPatch, capability: str, expected: set[str]
) -> None:
    calls: list[list[str]] = []

    def accept_hostname() -> None:
        pass

    monkeypatch.setattr(pod042_reconcile, "assert_hostname", accept_hostname)
    monkeypatch.setattr(pod042_reconcile, "run_command", calls.append)
    pod042_reconcile.run_local(capability, False)
    assert len(calls) == (2 if capability == "operator" else 1)
    command = calls[-1]
    assert {
        command[index + 1]
        for index, argument in enumerate(command)
        if argument == "--secret"
    } == expected


def test_containers_capability_has_real_prerequisites() -> None:
    assert pod042_reconcile.capabilities_for("containers") == (
        "repositories",
        "storage",
        "alerting",
        "containers",
    )
