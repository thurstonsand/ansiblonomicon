import os
from pathlib import Path
import runpy
import shlex
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
    secrets = tomllib.loads((ROOT / "fnox.toml").read_text())["secrets"]
    for task in tasks.values():
        commands = task.get("run", [])
        if isinstance(commands, str):
            commands = [commands]
        for command in commands:
            if "fnox-host" not in command or " exec " not in command:
                continue
            selected = task_secrets(command)
            assert selected
            assert all(secrets[name]["provider"] == "agent" for name in selected)
    assert "fnox-host" not in tasks["reconcile"]["run"]
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
