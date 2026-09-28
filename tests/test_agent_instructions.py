import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "bootstrap/targets"
PI = ".pi/agent/AGENTS.md"
FILES = {
    "ML-DFC6YK6VJQ": [".claude/CLAUDE.md", ".codex/AGENTS.md", PI],
    "Thurstons-MacBook-Pro": [
        ".claude/CLAUDE.md",
        ".codex/AGENTS.md",
        ".config/opencode/AGENTS.md",
        PI,
    ],
    "pod042": [
        ".claude/CLAUDE.md",
        ".codex/AGENTS.md",
        ".config/opencode/AGENTS.md",
        PI,
    ],
    "type-a-no2": [PI],
}


def render(home: Path, host: str, **extra: str) -> dict[str, str]:
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "MISE_CACHE_DIR": str(home / ".cache/mise"),
        "MISE_CONFIG_DIR": str(home / ".config/mise"),
        "MISE_DATA_DIR": str(home / ".local/share/mise"),
        "MISE_STATE_DIR": str(home / ".local/state/mise"),
        "MISE_SYSTEM_CONFIG_FILE": str(home / "absent-system.toml"),
        "MISE_GLOBAL_CONFIG_FILE": str(home / "absent-global.toml"),
        "MISE_CEILING_PATHS": str(TARGETS),
        "MISE_TRUSTED_CONFIG_PATHS": str(ROOT),
        "MISE_ENV": "agent-instructions",
        **extra,
    }
    subprocess.run(
        ["mise", "-C", str(TARGETS / host), "bootstrap", "--only", "dotfiles", "--yes"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        str(path.relative_to(home)): path.read_text()
        for path in home.rglob("*.md")
        if ".local" not in path.parts and path.parts[-2:] != (".agents", "local.md")
    }


@pytest.mark.parametrize("host", FILES)
def test_every_harness_receives_one_host_profile_render(
    host: str, tmp_path: Path
) -> None:
    rendered = render(tmp_path, host)

    work = host == "ML-DFC6YK6VJQ"
    assert sorted(rendered) == sorted(FILES[host])
    assert len(set(rendered.values())) == 1
    text = rendered[PI]
    assert text.startswith("# AGENTS.md\n\n## Persona: Unit 2B")
    assert "### Git" in text
    assert "### Delegation and model selection" in text
    assert "### Choosing thread modes" not in text
    assert ("claude-fable-5-1" in text) is not work
    assert ("request permission before firing off a Fable" in text) is not work
    assert "@~/.agents/local.md" not in text
    assert "\n\n\n" not in text


def test_local_instructions_are_referenced_when_deployed(tmp_path: Path) -> None:
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents/local.md").write_text("local")

    text = render(tmp_path, "ML-DFC6YK6VJQ")[PI]

    assert text.endswith("vice versa.\n\n@~/.agents/local.md\n")


def test_amp_guidance_swaps_git_and_delegation_for_thread_modes(
    tmp_path: Path,
) -> None:
    text = render(tmp_path, "Thurstons-MacBook-Pro", AMP_GUIDANCE="1")[
        ".codex/AGENTS.md"
    ]

    assert "## Persona: Unit 2B" in text
    assert "### Choosing thread modes" in text
    assert "`doppelclaude-opus-medium`" in text
    assert "### Git" not in text
    assert "### Delegation and model selection" not in text
    assert "\n\n\n" not in text
    assert len(text.strip()) <= 8000
