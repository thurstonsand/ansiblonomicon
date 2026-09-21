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
    assert set(environment_files) == set(pod042_reconcile.FULL_CAPABILITIES)
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
        pod042_reconcile.FULL_CAPABILITIES
    )


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


def test_apply_runs_mise_maintenance_before_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pod042_reconcile, "assert_hostname", Mock())
    monkeypatch.setattr(pod042_reconcile, "run_command", calls.append)

    pod042_reconcile.run_local("storage", check_mode=False)

    assert calls[0] == [
        "mise",
        "-C",
        str(pod042_reconcile.TARGET_ROOT),
        "run",
        "mise:maintain",
    ]
    assert calls[1][-2:] == ["bootstrap", "--yes"]


def test_terminal_theme_focused_apply_uses_only_canonical_root_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pod042_reconcile, "assert_hostname", Mock())
    monkeypatch.setattr(pod042_reconcile, "run_command", calls.append)

    pod042_reconcile.run_local("terminal-theme", check_mode=False)

    assert calls == [
        [
            "mise",
            "-C",
            str(pod042_reconcile.TARGET_ROOT),
            "run",
            "mise:maintain",
        ],
        [
            "mise",
            "-C",
            str(pod042_reconcile.ROOT),
            "run",
            "terminal-theme",
        ],
    ]


def test_terminal_theme_check_previews_canonical_dotfile_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pod042_reconcile, "assert_hostname", Mock())
    monkeypatch.setattr(pod042_reconcile, "run_command", calls.append)

    pod042_reconcile.run_local("terminal-theme", check_mode=True)

    assert calls == [
        [
            "mise",
            "-C",
            str(pod042_reconcile.ROOT),
            "run",
            "terminal-theme",
            "--check",
        ]
    ]


def test_git_client_focused_apply_runs_only_canonical_root_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pod042_reconcile, "assert_hostname", Mock())
    monkeypatch.setattr(pod042_reconcile, "run_command", calls.append)

    pod042_reconcile.run_local("git-client", check_mode=False)

    git_calls = [call for call in calls if call[-2:] == ["run", "git-client"]]
    assert len(git_calls) == 1
    assert not any(call[-2:] == ["bootstrap", "--yes"] for call in calls)
    assert pod042_reconcile.capabilities_for("git-client") == (
        "vcs-identity",
        "git-client",
    )


def test_jj_client_focused_apply_loads_identity_and_only_runs_root_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pod042_reconcile, "assert_hostname", Mock())
    monkeypatch.setattr(pod042_reconcile, "run_command", calls.append)

    pod042_reconcile.run_local("jj-client", check_mode=False)

    assert pod042_reconcile.capabilities_for("jj-client") == (
        "vcs-identity",
        "jj-client",
    )
    assert [call for call in calls if call[-2:] == ["run", "jj-client"]] == [
        ["mise", "-C", str(pod042_reconcile.ROOT), "run", "jj-client"]
    ]


def test_full_apply_runs_root_capabilities_after_prerequisite_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pod042_reconcile, "assert_hostname", Mock())
    monkeypatch.setattr(pod042_reconcile, "run_command", calls.append)
    monkeypatch.setattr(pod042_reconcile, "TARGET_ROOT", tmp_path)
    (tmp_path / "mise.doppelclaude.toml").write_text(
        '[vars]\ndoppelclaude_image = "example.com/doppelclaude@sha256:'
        + "a" * 64
        + '"\n'
    )

    pod042_reconcile.run_local(None, check_mode=False)

    theme_calls = [call for call in calls if call[-2:] == ["run", "terminal-theme"]]
    assert len(theme_calls) == 1
    assert calls.index(theme_calls[0]) > next(
        index for index, call in enumerate(calls) if call[-2:] == ["bootstrap", "--yes"]
    )
    main_bootstrap = next(call for call in calls if call[-2:] == ["bootstrap", "--yes"])
    environment = next(part for part in main_bootstrap if part.startswith("MISE_ENV="))
    assert "terminal-theme" not in environment.split("=", 1)[1].split(",")
    git_calls = [call for call in calls if call[-2:] == ["run", "git-client"]]
    assert len(git_calls) == 1
    assert calls.index(git_calls[0]) > calls.index(main_bootstrap)
    assert "git-client" not in environment.split("=", 1)[1].split(",")
    terminal_calls = [call for call in calls if call[-2:] == ["run", "terminal-tools"]]
    assert len(terminal_calls) == 1
    assert calls.index(terminal_calls[0]) > calls.index(main_bootstrap)
    shell_call = next(call for call in calls if call[-2:] == ["run", "shell"])
    assert calls.index(terminal_calls[0]) > calls.index(shell_call)
    assert "terminal-tools" not in environment.split("=", 1)[1].split(",")


@pytest.mark.parametrize(
    "image", ["", "example.com/app:latest", "example.com/app@sha256:abc"]
)
@pytest.mark.parametrize("check_mode", [True, False])
def test_doppelclaude_refuses_unpinned_image_before_any_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, image: str, check_mode: bool
) -> None:
    monkeypatch.setattr(pod042_reconcile, "assert_hostname", Mock())
    monkeypatch.setattr(pod042_reconcile, "TARGET_ROOT", tmp_path)
    (tmp_path / "mise.doppelclaude.toml").write_text(
        f'[vars]\ndoppelclaude_image = "{image}"\n'
    )
    run = Mock()
    monkeypatch.setattr(pod042_reconcile, "run_command", run)
    with pytest.raises(pod042_reconcile.ReconcileError, match="reviewed image@sha256"):
        pod042_reconcile.run_local("doppelclaude", check_mode)
    run.assert_not_called()


@pytest.mark.parametrize("check_mode", [True, False])
def test_doppelclaude_is_isolated_and_checks_prerequisites(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, check_mode: bool
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pod042_reconcile, "assert_hostname", Mock())
    monkeypatch.setattr(pod042_reconcile, "TARGET_ROOT", tmp_path)
    (tmp_path / "mise.doppelclaude.toml").write_text(
        '[vars]\ndoppelclaude_image = "example.com/doppelclaude@sha256:'
        + "b" * 64
        + '"\n'
    )
    monkeypatch.setattr(pod042_reconcile, "run_command", calls.append)
    pod042_reconcile.run_local("doppelclaude", check_mode)
    assert calls[0] == ["findmnt", "--mountpoint", "/mnt/black-box/docker"]
    assert calls[1] == ["sudo", "-n", "docker", "network", "inspect", "ingress"]
    assert len(calls) == 3
    plan = calls[2]
    assert "MISE_ENV=doppelclaude" in plan
    assert plan[-2:] == ["bootstrap", "plan" if check_mode else "--yes"]
    assert [plan[index + 1] for index, arg in enumerate(plan) if arg == "--secret"] == [
        "CLI_PROXY_API_KEY",
        "CLAUDE_CODE_OAUTH_TOKEN",
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

    assert len(calls) == 3
    assert calls[0][-2:] == ["run", "mise:maintain"]
    assert "MISE_ENV=base" in calls[1]
    assert calls[1][-4:] == ["bootstrap", "--only", "packages", "--yes"]
    assert calls[2][-2:] == ["bootstrap", "--yes"]
    assert "--only" not in calls[2]


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
    assert len(calls) == (3 if capability == "operator" else 2)
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
