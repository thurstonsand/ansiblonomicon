from collections.abc import Sequence
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import sys
import tomllib
from typing import Any

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
        (MODULE_PATH.parents[1] / "bootstrap/targets/pod042/base/mise.toml").read_text()
    )
    storage = tomllib.loads(
        (
            MODULE_PATH.parents[1] / "bootstrap/targets/pod042/storage/mise.toml"
        ).read_text()
    )

    assert target["settings"]["jobs"] == 1
    assert target["settings"]["system_packages"]["managers"] == ["apt"]
    assert target["bootstrap"]["users"]["thurstonsand"]["groups"] == ["sudo"]
    assert target["bootstrap"]["repos"][pod042_reconcile.REMOTE_CHECKOUT] == {
        "url": "https://github.com/thurstonsand/ansiblonomicon.git"
    }
    assert (
        base["bootstrap"]["files"]["/etc/ssh/sshd_config.d/00-ansiblonomicon.conf"][
            "content"
        ]
        == "PasswordAuthentication no\nPermitRootLogin no\nPubkeyAuthentication yes\n"
    )
    assert target["bootstrap"]["config_roots"] == ["base", "storage"]
    assert target["bootstrap"]["packages"]["apt:zfsutils-linux"] == "latest"
    assert storage["bootstrap"]["services"]["zfs-import-cache"]["enabled"] is True
    assert storage["bootstrap"]["services"]["zfs-mount"]["enabled"] is True


def test_local_deploy_revision_requires_clean_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def dirty_git_output(_repo: Path, *_args: str) -> str:
        return "?? recovery-edit"

    monkeypatch.setattr(pod042_reconcile, "git_output", dirty_git_output)

    with pytest.raises(
        pod042_reconcile.ReconcileError, match="workstation checkout has local changes"
    ):
        pod042_reconcile.local_deploy_revision(Path("/repo"))


def test_local_deploy_revision_requires_pushed_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values: dict[tuple[str, ...], str] = {
        ("status", "--porcelain"): "",
        ("symbolic-ref", "--quiet", "--short", "HEAD"): "main",
        (
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
        ): "origin/main",
        ("rev-parse", "HEAD"): "local",
        ("rev-parse", "origin/main"): "remote",
    }

    def fake_git_output(_repo: Path, *args: str) -> str:
        return values[args]

    monkeypatch.setattr(pod042_reconcile, "git_output", fake_git_output)

    with pytest.raises(pod042_reconcile.ReconcileError, match="not exactly"):
        pod042_reconcile.local_deploy_revision(Path("/repo"))


def test_fast_forward_remote_checkout_targets_exact_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def remote_git(
        _host: str, *args: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        outputs: dict[tuple[str, ...], str] = {
            ("status", "--porcelain"): "",
            ("symbolic-ref", "--quiet", "--short", "HEAD"): "main\n",
            ("rev-parse", "HEAD"): "old\n",
            ("fetch", "origin", "main"): "",
            ("rev-parse", "origin/main"): "new\n",
            ("merge-base", "--is-ancestor", "old", "new"): "",
            ("merge", "--ff-only", "new"): "",
        }
        return completed(outputs[args], 0)

    monkeypatch.setattr(pod042_reconcile, "remote_git", remote_git)

    pod042_reconcile.fast_forward_remote_checkout("pod042", "main", "new")

    assert calls[-1] == ("merge", "--ff-only", "new")


def test_fast_forward_rejects_diverged_remote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def remote_git(
        _host: str, *args: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        outputs: dict[tuple[str, ...], str] = {
            ("status", "--porcelain"): "",
            ("symbolic-ref", "--quiet", "--short", "HEAD"): "main\n",
            ("rev-parse", "HEAD"): "remote\n",
            ("fetch", "origin", "main"): "",
            ("rev-parse", "origin/main"): "local\n",
        }
        if args[:2] == ("merge-base", "--is-ancestor"):
            return completed(returncode=1)
        return completed(outputs[args])

    monkeypatch.setattr(pod042_reconcile, "remote_git", remote_git)

    with pytest.raises(pod042_reconcile.ReconcileError, match="cannot fast-forward"):
        pod042_reconcile.fast_forward_remote_checkout("pod042", "main", "local")


def test_check_uses_native_bootstrap_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def accept_hostname(_host: str | None) -> None:
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
            "mise",
            "-C",
            str(pod042_reconcile.TARGET_ROOT),
            "bootstrap",
            "plan",
        ]
    ]


def test_initial_remote_bootstrap_stages_matching_mise() -> None:
    command = pod042_reconcile.remote_bootstrap_command(
        "10.10.10.99", None, check_mode=False, install_mise=True
    )

    assert "--host" in command
    assert "thurstonsand@10.10.10.99" in command
    assert "--source" in command
    assert "targets/pod042" in command
    assert "--remote-mise" not in command
    assert not any(argument.startswith("--install-mise") for argument in command)
    assert "ansible" not in " ".join(command)


def test_remote_commands_can_override_the_identity_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(pod042_reconcile.IDENTITY_AGENT_ENV, "/tmp/operator-agent")

    ssh = pod042_reconcile.ssh_command("pod042", ["true"])
    bootstrap = pod042_reconcile.remote_bootstrap_command(
        "pod042", None, check_mode=False, install_mise=False
    )

    assert "IdentityAgent=/tmp/operator-agent" in ssh
    assert "IdentityAgent=/tmp/operator-agent" in bootstrap


def test_normal_remote_bootstrap_uses_managed_system_mise() -> None:
    command = pod042_reconcile.remote_bootstrap_command(
        "pod042", None, check_mode=False, install_mise=False
    )

    index = command.index("--remote-mise")
    assert command[index + 1] == "/usr/local/bin/mise"


def test_wrong_local_hostname_fails_before_reconcile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pod042_reconcile.socket, "gethostname", lambda: "not-pod042")

    def wrong_remote_hostname(_host: str, _argv: Sequence[str]) -> str:
        return "not-pod042"

    monkeypatch.setattr(pod042_reconcile, "remote_output", wrong_remote_hostname)

    with pytest.raises(pod042_reconcile.ReconcileError, match="requires hostname"):
        pod042_reconcile.run(["--host", "10.10.10.99", "--initial"])


def test_check_and_update_mise_are_incompatible() -> None:
    with pytest.raises(pod042_reconcile.ReconcileError, match="cannot be combined"):
        pod042_reconcile.run(["--check", "--update-mise"])
