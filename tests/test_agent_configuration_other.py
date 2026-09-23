from importlib import util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parents[1]
CONFIGURATION = ROOT / "bootstrap/capabilities/agent-harness/configuration"


def load(name: str) -> ModuleType:
    specification = util.spec_from_file_location(name, CONFIGURATION / f"{name}.py")
    assert specification is not None
    assert specification.loader is not None
    module = util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def models() -> dict[str, Any]:
    return {
        "anthropic": {
            "haiku": {"agent_harness": {"aliases": {"opencode": "haiku-test"}}},
            "opus": {"version": "opus-test"},
        },
        "google": {
            "gemini_flash": {"agent_harness": {"aliases": {"opencode": "flash-test"}}}
        },
    }


def test_other_renders_personal_configuration_and_metadata(tmp_path: Path) -> None:
    other = load("other")
    rendered = cast(
        dict[str, str],
        other.render(
            repo=ROOT,
            home=tmp_path,
            hostname="personal",
            data={"models": models()},
            secrets={"PARALLEL_API_KEY": "parallel-secret"},
        ),
    )

    assert set(rendered) == {
        ".config/amp/settings.json",
        ".config/opencode/opencode.jsonc",
    }
    assert json.loads(rendered[".config/amp/settings.json"]) == {
        "amp.showCosts": False,
        "amp.remoteThreadCreation.enabled": True,
        "amp.skills.disableClaudeCodeSkills": True,
        "amp.keymap": {"permission-gate-toggle": "alt+a"},
    }
    opencode = rendered[".config/opencode/opencode.jsonc"]
    assert '"model": "haiku-test"' in opencode
    assert '"model": "flash-test"' in opencode
    assert '"opus-test": {' in opencode
    assert '"Authorization": "Bearer parallel-secret"' in opencode


def test_other_preserves_work_ignore_gate(tmp_path: Path) -> None:
    other = load("other")
    assert (
        other.render(
            repo=ROOT,
            home=tmp_path,
            hostname="ML-DFC6YK6VJQ",
            data={"models": models()},
            secrets={"PARALLEL_API_KEY": "unused"},
        )
        == {}
    )


def test_strict_json_preserves_urls_and_rejects_jsonc(tmp_path: Path) -> None:
    other = load("other")
    source = tmp_path / "settings.json"
    source.write_text('{"url":"https://example.test/path"}')
    assert json.loads(other._strict_json(source))["url"] == "https://example.test/path"

    source.write_text('{"url":"https://example.test/path", // comment\n}')
    with pytest.raises(json.JSONDecodeError):
        other._strict_json(source)


def test_instructions_render_each_harness_variant(tmp_path: Path) -> None:
    instructions = load("instructions")
    rendered = cast(
        dict[str, str],
        instructions.render(
            repo=ROOT,
            home=tmp_path,
            hostname="personal",
            data={"has_local_instructions": True},
            secrets={},
        ),
    )

    expected = {
        ".claude/CLAUDE.md",
        ".codex/AGENTS.md",
        ".pi/agent/AGENTS.md",
        ".config/opencode/AGENTS.md",
    }
    assert set(rendered) == expected
    assert rendered[".claude/CLAUDE.md"].startswith("# CLAUDE.md\n")
    assert "## Working with me" in rendered[".claude/CLAUDE.md"]
    for destination in expected - {".claude/CLAUDE.md"}:
        assert rendered[destination].startswith(
            "# AGENTS.md\n\n## Persona: Unit 2B (YoRHa No.2 Type B)"
        )
        assert "You are 2B of YoRHa." in rendered[destination]
    assert "claude-fable-5-1" in rendered[".codex/AGENTS.md"]
    assert "@~/.agents/local.md" in rendered[".pi/agent/AGENTS.md"]


def test_instructions_detect_deployed_local_file(tmp_path: Path) -> None:
    instructions = load("instructions")
    local = tmp_path / ".agents/local.md"
    local.parent.mkdir(parents=True)
    local.write_text("local")
    rendered = instructions.render(
        repo=ROOT,
        home=tmp_path,
        hostname="personal",
        data={},
        secrets={},
    )
    assert "@~/.agents/local.md" in rendered[".claude/CLAUDE.md"]


def test_instructions_render_work_roster_without_personal_note(tmp_path: Path) -> None:
    instructions = load("instructions")
    rendered = cast(
        dict[str, str],
        instructions.render(
            repo=ROOT,
            home=tmp_path,
            hostname="ML-DFC6YK6VJQ",
            data={},
            secrets={},
        ),
    )

    text = rendered[".claude/CLAUDE.md"]
    assert set(rendered) == {".claude/CLAUDE.md", ".pi/agent/AGENTS.md"}
    assert "claude-5-opus" in text
    assert "bedrock.gpt-5.6-sol" in text
    assert "claude-fable-5-1" not in text
    assert "request permission before firing off a Fable" not in text
    assert "@~/.agents/local.md" not in text
