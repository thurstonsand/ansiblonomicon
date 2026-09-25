from importlib import util
import json
from pathlib import Path
from types import ModuleType
from typing import cast

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


def test_strict_json_preserves_urls_and_rejects_jsonc(tmp_path: Path) -> None:
    amp = load("amp")
    source = tmp_path / "settings.json"
    source.write_text('{"url":"https://example.test/path"}')
    assert json.loads(amp._strict_json(source))["url"] == "https://example.test/path"

    source.write_text('{"url":"https://example.test/path", // comment\n}')
    with pytest.raises(json.JSONDecodeError):
        amp._strict_json(source)


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
        harnesses=["claude"],
    )
    assert "@~/.agents/local.md" in rendered[".claude/CLAUDE.md"]


def test_work_instructions_carry_no_personal_content(tmp_path: Path) -> None:
    instructions = load("instructions")
    rendered = cast(
        dict[str, str],
        instructions.render(
            repo=ROOT,
            home=tmp_path,
            hostname="ML-DFC6YK6VJQ",
            data={},
            secrets={},
            harnesses=["claude", "pi"],
        ),
    )

    text = rendered[".claude/CLAUDE.md"]
    assert set(rendered) == {".claude/CLAUDE.md", ".pi/agent/AGENTS.md"}
    assert "claude-fable-5-1" not in text
    assert "request permission before firing off a Fable" not in text
    assert "@~/.agents/local.md" not in text
