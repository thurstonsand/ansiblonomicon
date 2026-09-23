import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pi_configuration",
    ROOT / "bootstrap/capabilities/agent-harness/configuration/pi.py",
)
assert SPEC and SPEC.loader
pi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pi)


def model(version: str, alias: str) -> dict[str, Any]:
    return {"version": version, "agent_harness": {"aliases": {"pi": alias}}}


def data() -> dict[str, Any]:
    return {
        "models": {
            "anthropic": {
                "opus": model("opus-version", "doppel/opus"),
                "fable": model("fable-version", "doppel/fable"),
            },
            "openai": {
                "gpt_astra": model("astra-version", "codex/astra"),
                "gpt_sol": model("sol-version", "codex/sol"),
                "gpt_luna": model("luna-version", "codex/luna"),
            },
        },
        "fonts": {"mono": "Test Mono"},
        "developDir": "Develop",
    }


def rendered(tmp_path: Path, hostname: str, values: dict[str, Any] | None = None):
    return pi.render(
        repo=ROOT,
        home=tmp_path,
        hostname=hostname,
        data=values or data(),
        secrets={},
    )


def test_personal_mac_uses_local_packages_and_canonical_aliases(tmp_path: Path) -> None:
    result = rendered(tmp_path, "personal-mac")
    settings = json.loads(result[".pi/agent/settings.json"])

    assert settings["defaultModel"] == "opus-version"
    assert settings["enabledModels"] == [
        "doppel/opus:medium",
        "doppel/fable:medium",
        "codex/astra:medium",
        "codex/sol:medium",
    ]
    assert str(tmp_path / "Develop/pi-permissions") in settings["packages"]
    assert (
        settings["sessions"]["autoTitle"]["prompt"]
        == (
            ROOT / "bootstrap/capabilities/agent-harness/session-title-prompt.txt"
        ).read_text()
    )
    assert ".pi/agent/mcp.json" not in result
    assert (
        result[".pi/agent/extensions/glimpse-companion/companion/font-family.txt"]
        == "Test Mono\n"
    )


def test_pod042_uses_npm_packages_and_disables_companion(tmp_path: Path) -> None:
    result = rendered(tmp_path, "pod042")
    settings = json.loads(result[".pi/agent/settings.json"])
    assert "npm:pi-permissions" in settings["packages"]
    assert not any(str(item).startswith("/Users/") for item in settings["packages"])
    assert settings["glimpse"]["companion"]["enabled"] is False
    assert ".pi/agent/mcp.json" not in result


def test_work_gateway_models_packages_and_runtime(tmp_path: Path) -> None:
    values = data()
    values.update(
        {
            "work_gateway": {
                "anthropic_provider": "corp-anthropic",
                "openai_provider": "corp-openai",
                "base_url": "https://gateway.test",
            },
            "piWorkPackages": ["npm:corporate"],
            "work_models": {
                name: {
                    "version": f"{name}-v[1m]",
                    "display_name": name,
                    "pi_alias": f"corp/{name}",
                    "cost": {"input": 1, "output": 2, "cacheRead": 3, "cacheWrite": 4},
                    "context_window": 100,
                    "max_output": 20,
                    **({"supports_temperature": False} if name == "opus" else {}),
                }
                for name in (
                    "opus",
                    "sonnet",
                    "haiku",
                    "gpt_sol",
                    "gpt_terra",
                    "gpt_luna",
                )
            },
        }
    )
    result = pi.render(
        repo=ROOT,
        home=tmp_path,
        hostname=pi.WORK_HOST,
        data=values,
        secrets={"ANTHROPIC_AUTH_TOKEN": "secret-token"},
    )
    settings = json.loads(result[".pi/agent/settings.json"])
    providers = json.loads(result[".pi/agent/models.json"])["providers"]
    assert settings["defaultProvider"] == "corp-openai"
    assert settings["packages"][0] == "npm:corporate"
    assert "doppelclaude" not in settings
    assert ".pi/agent/pi-smart-btw.json" not in result
    assert providers["corp-anthropic"]["apiKey"] == "secret-token"
    assert providers["corp-anthropic"]["models"][0]["id"] == "opus-v"
    assert 'pi_bin="$HOME/.local/libexec/pi"' in result[".local/bin/pi"]


def test_personal_packages_follow_configured_absolute_develop_dir(
    tmp_path: Path,
) -> None:
    values = data()
    values["developDir"] = "/srv/code"
    settings = json.loads(
        rendered(tmp_path, "personal-mac", values)[".pi/agent/settings.json"]
    )
    assert "/srv/code/pi-permissions" in settings["packages"]
    assert "/srv/code/wt/plugins/pi" in settings["packages"]


def test_auth_preserves_foreign_entries_and_retires_only_managed(
    tmp_path: Path,
) -> None:
    auth = tmp_path / ".pi/agent/auth.json"
    auth.parent.mkdir(parents=True)
    auth.write_text(
        json.dumps({"anthropic": {"type": "oauth"}, "custom": {"future": True}})
    )
    merged = json.loads(rendered(tmp_path, "personal-mac")[".pi/agent/auth.json"])
    assert merged == {"custom": {"future": True}}


def test_invalid_auth_refuses_to_render(tmp_path: Path) -> None:
    auth = tmp_path / ".pi/agent/auth.json"
    auth.parent.mkdir(parents=True)
    auth.write_text("not json")
    with pytest.raises(ValueError, match="invalid JSON; refusing to overwrite"):
        rendered(tmp_path, "personal-mac")


def test_live_changelog_and_explicit_mcp_are_preserved(tmp_path: Path) -> None:
    settings = tmp_path / ".pi/agent/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"lastChangelogVersion": "9.7.3"}))
    values = data()
    values["pi_mcp_json"] = ['{"one":{"command":"one"}}', '{"two":{"command":"two"}}']
    result = rendered(tmp_path, "personal-mac", values)
    assert (
        json.loads(result[".pi/agent/settings.json"])["lastChangelogVersion"] == "9.7.3"
    )
    assert json.loads(result[".pi/agent/mcp.json"])["mcpServers"] == {
        "one": {"command": "one"},
        "two": {"command": "two"},
    }
