import getpass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
from typing import Any
from unittest.mock import Mock

import pytest
from test_user_tools_capability import isolated_env

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/pod042_reconcile.py"
SPEC = spec_from_file_location("pod042_reconcile", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
pod042_reconcile: Any = module_from_spec(SPEC)
sys.modules[SPEC.name] = pod042_reconcile
SPEC.loader.exec_module(pod042_reconcile)
MISE = shutil.which("mise")
assert MISE is not None


def test_capability_environments_are_explicit_and_disjoint() -> None:
    target_root = MODULE_PATH.parents[1] / "bootstrap/targets/pod042"
    environment_files = {
        path.stem.removeprefix("mise."): tomllib.loads(path.read_text())
        for path in target_root.glob("mise.*.toml")
        if not path.name.endswith(".local.toml")
    }
    bootstrap_capabilities = tuple(
        capability
        for capability in pod042_reconcile.FULL_CAPABILITIES
        if capability != "agent-harness"
    )
    assert set(environment_files) == set(bootstrap_capabilities)
    assert "vcs-identity" not in pod042_reconcile.CAPABILITIES

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
        bootstrap_capabilities
    )


@pytest.mark.skipif(
    subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode != 0,
    reason="system-file apply requires passwordless sudo",
)
def test_production_operator_and_remote_dotfiles_apply_and_repeat(
    tmp_path: Path,
) -> None:
    assert MISE is not None
    production = MODULE_PATH.parents[1] / "bootstrap/targets/pod042"
    target = tmp_path / "target"
    home = tmp_path / "home"
    target.mkdir()
    home.mkdir()
    for capability in ("operator", "remote-development"):
        shutil.copytree(production / capability, target / capability)
        source = (production / f"mise.{capability}.toml").read_text()
        rebased = source.replace("/home/thurstonsand", str(home)).replace(
            '"thurstonsand"', f'"{getpass.getuser()}"'
        )
        (target / f"mise.{capability}.toml").write_text(rebased)
    (target / "mise.toml").write_text('min_version = "2026.9.11"\n')
    env = isolated_env(home, target, "/usr/bin:/bin")
    env["MISE_ENV"] = "operator,remote-development"
    command = [
        MISE,
        "-C",
        str(target),
        "bootstrap",
        "--only",
        "files,dotfiles",
        "--force-dotfiles",
    ]

    preview = subprocess.run(
        [*command, "--dry-run"], env=env, capture_output=True, text=True
    )
    assert preview.returncode == 0, preview.stderr
    assert not (home / ".config/mise/config.toml").exists()

    applied = subprocess.run(
        [*command, "--yes"], env=env, capture_output=True, text=True
    )
    assert applied.returncode == 0, applied.stderr
    operator_config = home / ".config/mise/config.toml"
    npmrc = home / ".config/t3code/npmrc"
    assert operator_config.is_symlink()
    assert operator_config.resolve() == target / "operator/mise.toml"
    assert npmrc.is_symlink()
    assert npmrc.resolve() == target / "remote-development/t3.npmrc"
    copied = [
        home / ".config/systemd/user/amp-remote.service",
        home / ".config/systemd/user/herdr.service",
        home / ".config/systemd/user/t3code.service.d/operator.conf",
    ]
    assert all(path.is_file() and not path.is_symlink() for path in copied)
    before = [(path.stat().st_ino, path.stat().st_mtime_ns) for path in copied]
    repeated = subprocess.run(
        [*command, "--yes"], env=env, capture_output=True, text=True
    )
    assert repeated.returncode == 0, repeated.stderr
    assert [(path.stat().st_ino, path.stat().st_mtime_ns) for path in copied] == before


def test_vars_only_identity_is_not_a_public_capability() -> None:
    with pytest.raises(
        pod042_reconcile.ReconcileError, match="unknown pod042 capability"
    ):
        pod042_reconcile.capabilities_for("vcs-identity")


def test_incus_capability_closure() -> None:
    assert pod042_reconcile.capabilities_for("incus") == (
        "network",
        "repositories",
        "storage",
        "datasets",
        "incus",
    )


def test_ssh_client_capability_includes_pod042_key_overlay() -> None:
    assert pod042_reconcile.capabilities_for("ssh-client") == (
        "ssh-client",
        "ssh-client-pod042",
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


def test_containers_capability_has_real_prerequisites() -> None:
    assert pod042_reconcile.capabilities_for("containers") == (
        "repositories",
        "storage",
        "alerting",
        "containers",
    )
