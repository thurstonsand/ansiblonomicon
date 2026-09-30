from pathlib import Path
import shlex
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
        **tomllib.loads((ROOT / "fnox.omarchy.toml").read_text())["secrets"],
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


@pytest.mark.parametrize("stack,provider", [("edge", CLOUDFLARE), ("unifi", UNIFI)])
def test_tofu_tasks_select_only_backend_and_own_provider(
    stack: str, provider: set[str]
) -> None:
    tasks = tomllib.loads((ROOT / "mise.toml").read_text())["tasks"]
    assert task_secrets(tasks[f"{stack}:init"]["run"]) == BACKEND
    for operation in ("plan", "apply"):
        assert task_secrets(tasks[f"{stack}:{operation}"]["run"]) == BACKEND | provider
