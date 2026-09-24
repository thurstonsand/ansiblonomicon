import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import sys
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"}
UNIFI = {
    "UNIFI_USERNAME",
    "UNIFI_PASSWORD",
    "UNIFI_WAN_MAC_OVERRIDE",
    "YORHA_PASSPHRASE",
    "LUNAR_TEAR_PASSPHRASE",
    "THE_VILLAGE_PASSPHRASE",
    "SCANNERS_PASSPHRASE",
}
CLOUDFLARE = {"CLOUDFLARE_API_TOKEN", "PARENT_HOME_IP"}


def task_secrets(command: str) -> set[str]:
    arguments = shlex.split(command)
    return {
        arguments[index + 1]
        for index, argument in enumerate(arguments)
        if argument == "--secret"
    }


def test_current_scoped_tasks_only_request_agent_credentials():
    tasks = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"]
    secrets = {
        **tomllib.loads((ROOT / "fnox.toml").read_text())["secrets"],
        **tomllib.loads((ROOT / "fnox.pod042.toml").read_text())["secrets"],
    }
    laptop_tasks = {
        "reconcile",
        "reconcile:laptop",
        "mac-apps",
        "shell",
        "terminal-theme",
        "desktop-tools",
        "editor-config",
        "work-local",
    }
    for task_name, task in tasks.items():
        commands = task.get("run", [])
        if isinstance(commands, str):
            commands = [commands]
        for command in commands:
            if "fnox-host" not in command or " exec " not in command:
                continue
            # Covered by executing every host/check branch below; its secret
            # arguments are selected by hostname rather than statically.
            if task_name == "agent-config":
                continue
            if task_name in laptop_tasks:
                continue
            selected = task_secrets(command)
            assert selected
            assert all(secrets[name]["provider"] == "agent" for name in selected)


def run_agent_config_task(
    tmp_path: Path,
    host: str,
    *,
    check: bool = False,
    real_secrets: bool = False,
) -> tuple[list[str] | None, list[str]]:
    project = tmp_path / "repo with spaces"
    home = tmp_path / "home with spaces"
    bin_dir = tmp_path / "stub bin"
    calls = tmp_path / "calls"
    for directory in (
        project / "scripts",
        project / ".venv/bin",
        project / "bootstrap/capabilities/agent-harness/configuration",
        home,
        bin_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    (bin_dir / "hostname").write_text(
        f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(host)}\n"
    )
    (project / "scripts/fnox-host").write_text(
        """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["CALLS"], "a") as stream:
    stream.write(json.dumps(["fnox", *sys.argv[1:]]) + "\\n")
separator = sys.argv.index("--")
os.execv(sys.argv[separator + 1], sys.argv[separator + 1:])
"""
    )
    (project / ".venv/bin/python").write_text(
        """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["CALLS"], "a") as stream:
    stream.write(json.dumps(["python", *sys.argv[1:]]) + "\\n")
"""
    )
    for executable in (
        bin_dir / "hostname",
        project / "scripts/fnox-host",
        project / ".venv/bin/python",
    ):
        executable.chmod(0o755)

    task = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"]["agent-config"]
    environment = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "MISE_PROJECT_ROOT": str(project),
        "HOME": str(home),
        "CALLS": str(calls),
    }
    if check:
        environment["usage_check"] = "1"
    if real_secrets:
        environment["usage_real_secrets"] = "1"
    subprocess.run(["sh", "-c", task["run"]], env=environment, check=True)
    recorded = [json.loads(line) for line in calls.read_text().splitlines()]
    fnox = next((call for call in recorded if call[0] == "fnox"), None)
    python = next(call for call in recorded if call[0] == "python")
    return fnox, python


@pytest.mark.parametrize(
    ("host", "expected_secrets"),
    [
        ("Thurstons-MacBook-Pro", ["CLI_PROXY_API_KEY", "PARALLEL_API_KEY"]),
        ("pod042", ["CLI_PROXY_API_KEY", "PARALLEL_API_KEY"]),
        ("ML-DFC6YK6VJQ", ["ANTHROPIC_AUTH_TOKEN"]),
    ],
)
def test_agent_config_task_scopes_secrets_and_preserves_argv(
    tmp_path: Path, host: str, expected_secrets: list[str]
) -> None:
    fnox, python = run_agent_config_task(tmp_path, host)
    assert fnox is not None
    assert fnox[1 : fnox.index("--")] == [
        "exec",
        *(argument for secret in expected_secrets for argument in ("--secret", secret)),
    ]
    project = tmp_path / "repo with spaces"
    assert python == [
        "python",
        str(project / "bootstrap/capabilities/agent-harness/configuration/deploy.py"),
        "--repo",
        str(project),
        "--home",
        str(tmp_path / "home with spaces"),
        "--hostname",
        host,
    ]


def test_agent_config_placeholder_check_bypasses_fnox(tmp_path: Path) -> None:
    fnox, python = run_agent_config_task(tmp_path, "Thurstons-MacBook-Pro", check=True)
    assert fnox is None
    assert python[-1] == "--check"


def test_agent_config_real_secret_check_uses_fnox_and_both_flags(
    tmp_path: Path,
) -> None:
    fnox, python = run_agent_config_task(
        tmp_path, "pod042", check=True, real_secrets=True
    )
    assert fnox is not None
    assert python[-2:] == ["--check", "--real-secrets"]


def test_each_capability_task_requests_only_its_own_secrets():
    tasks = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"]
    expected: dict[str, set[str]] = {
        "ssh-client": {"POD042_GIT_SSH_PRIVATE_KEY", "POD042_GIT_SSH_PUBLIC_KEY"},
        "desktop-tools": set(),
        "editor-config": {
            "CLI_PROXY_API_KEY",
            "CF_ACCESS_CLIENT_ID",
            "CF_ACCESS_CLIENT_SECRET",
        },
        "work-local": {"HOMEBREW_SUDO_ASKPASS_PASS_WORK"},
        "terminal-theme": {"$sudo_secret"},
        "mac-apps": {"$sudo_secret"},
    }
    assert {name: task_secrets(tasks[name]["run"]) for name in expected} == expected
    # The umbrella task delegates, so it must never open one wide secret scope itself.
    assert "fnox-host" not in tasks["reconcile:laptop"]["run"]


@pytest.mark.parametrize("stack,provider", [("edge", CLOUDFLARE), ("unifi", UNIFI)])
def test_tofu_tasks_select_only_backend_and_own_provider(
    stack: str, provider: set[str]
) -> None:
    tasks = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"]
    assert task_secrets(tasks[f"{stack}:init"]["run"]) == BACKEND
    for operation in ("plan", "apply"):
        assert task_secrets(tasks[f"{stack}:{operation}"]["run"]) == BACKEND | provider


@pytest.mark.parametrize(
    "stack,provider", [("cloudflare", CLOUDFLARE), ("unifi", UNIFI)]
)
@pytest.mark.parametrize("operation", ["init", "plan", "apply"])
def test_tofu_adapter_does_not_require_unrelated_credentials(
    monkeypatch: pytest.MonkeyPatch,
    stack: str,
    provider: set[str],
    operation: str,
) -> None:
    environment = {name: f"sentinel-{name}" for name in BACKEND}
    if operation != "init":
        environment.update({name: f"sentinel-{name}" for name in provider})
    monkeypatch.setattr(os, "environ", environment)
    monkeypatch.setattr(sys, "argv", ["tofu.py", stack, operation])
    calls: list[tuple[str, list[str]]] = []

    def record_exec(binary: str, args: list[str]) -> None:
        calls.append((binary, args))

    monkeypatch.setattr(os, "execvp", record_exec)
    runpy.run_path(str(ROOT / "scripts/tofu.py"), run_name="__main__")
    assert calls == [("tofu", ["tofu", operation])]
    mapped = {key for key in environment if key.startswith("TF_VAR_")}
    assert len(mapped) == (0 if operation == "init" else len(provider))
