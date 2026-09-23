import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]


def _module() -> ModuleType:
    path = ROOT / "bootstrap/capabilities/agent-harness/configuration/claude.py"
    spec = importlib.util.spec_from_file_location("agent_configuration_claude", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _data() -> dict[str, object]:
    return {
        "models": {
            "anthropic": {
                "opus": {"agent_harness": {"aliases": {"claude": "declared-opus"}}},
                "sonnet": {"version": "declared-sonnet"},
            }
        },
        "work_models": {"fast": {"id": "work-fast"}},
        "developDir": "code",
        "aigEnabled": True,
    }


def test_render_merges_overlay_hooks_and_preserves_live_model_and_order(
    tmp_path: Path,
) -> None:
    module = _module()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    local = repo / "bootstrap/capabilities/agent-harness/local/pod042"
    local.mkdir(parents=True)
    (repo / "ansible").mkdir()
    (repo / "ansible/session-title-prompt.txt").write_text("Name it.\n")
    (local / "claude-settings-overlay.json").write_text(
        '{"permissions":{"defaultMode":"ask","deny":null},'
        '"model":"${work_models.fast.id}","overlayOnly":7}'
    )
    (local / "statusline-usage.sh").write_text(
        "render_section_usage() { echo usage; }\n"
    )
    settings_dir = home / ".claude"
    settings_dir.mkdir(parents=True)
    (settings_dir / "settings.json").write_text(
        '{"model":"live-choice","permissions":{"defaultMode":"old"},"foreign":true}'
    )
    hooks = home / ".cache/ansiblonomicon-harness/hooks"
    hooks.mkdir(parents=True)
    (hooks / "b.json").write_text(
        '{"hooks":{"SessionStart":[{"matcher":"foreign"}],"Novel":[{"hooks":[]}]}}'
    )

    rendered = module.render(
        repo=repo,
        home=home,
        hostname="pod042",
        data=_data(),
        secrets={"CLI_PROXY_API_KEY": "secret-token"},
    )
    settings = json.loads(rendered[".claude/settings.json"])

    assert list(settings)[:2] == ["model", "permissions"]
    assert settings["model"] == "live-choice"
    assert settings["permissions"]["defaultMode"] == "ask"
    assert "deny" not in settings["permissions"]
    assert settings["overlayOnly"] == 7
    assert "foreign" not in settings
    assert settings["hooks"]["SessionStart"][-1] == {"matcher": "foreign"}
    assert settings["hooks"]["Novel"] == [{"hooks": []}]
    assert (
        "render_section_usage() { echo usage; }"
        in rendered[".claude/scripts/statusline.sh"]
    )
    assert 'MODEL = "declared-sonnet"' in rendered[".claude/hooks/_config.py"]
    assert 'TOKEN = "secret-token"' in rendered[".claude/hooks/_config.py"]
    assert rendered[".claude/output-styles/2b.md"].startswith("---\nname: 2B\n")
    assert ".claude/CLAUDE.md" not in rendered


def test_malformed_configured_hook_fragment_is_refused(tmp_path: Path) -> None:
    module = _module()
    hooks = tmp_path / "home/.cache/ansiblonomicon-harness/hooks"
    hooks.mkdir(parents=True)
    malformed = hooks / "broken.json"
    malformed.write_text("not json")

    with pytest.raises(
        ValueError, match=r"broken\.json: invalid configured hook fragment"
    ):
        module.render(
            repo=tmp_path / "repo",
            home=tmp_path / "home",
            hostname="pod042",
            data=_data(),
            secrets={"CLI_PROXY_API_KEY": "secret-token"},
        )


def test_fresh_work_host_uses_declared_model_and_auth_secret(tmp_path: Path) -> None:
    module = _module()
    repo = tmp_path / "repo"
    rendered = module.render(
        repo=repo,
        home=tmp_path / "home",
        hostname="ML-DFC6YK6VJQ",
        data=_data(),
        secrets={"ANTHROPIC_AUTH_TOKEN": "anthropic"},
    )
    settings = json.loads(rendered[".claude/settings.json"])
    assert settings["model"] == "declared-opus"
    assert settings["env"]["ANTHROPIC_AUTH_TOKEN"] == "anthropic"
    assert "render_section_usage" not in rendered[".claude/scripts/statusline.sh"]
    assert ".claude/hooks/_config.py" not in rendered


def test_title_entrypoints_load_runtime_home_config_through_deployed_symlinks(
    tmp_path: Path,
) -> None:
    source = (
        ROOT / "bootstrap/capabilities/agent-harness/configuration/assets/claude/hooks"
    )
    home = tmp_path / "home"
    hooks = home / ".claude/hooks"
    hooks.mkdir(parents=True)
    (hooks / "_config.py").write_text(
        'API_URL = "unused"\nMAX_CONTEXT_BYTES = 1\nMODEL = "test"\n'
        'TITLE_PROMPT = "test"\nTOKEN = "synthetic"\n'
    )
    for name in ("_common.py", "derive-title.py", "retitle.py"):
        (hooks / name).symlink_to(source / name)

    environment = {**os.environ, "HOME": str(home)}
    derived = subprocess.run(
        [sys.executable, str(hooks / "derive-title.py")],
        input=json.dumps({"agent_id": "subagent"}),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert derived.returncode == 0, derived.stderr
    retitled = subprocess.run(
        [sys.executable, str(hooks / "retitle.py")],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert retitled.returncode == 1
    assert retitled.stderr == "retitle: session_id required as first argument\n"


def test_malformed_live_settings_are_refused(tmp_path: Path) -> None:
    module = _module()
    repo = tmp_path / "repo"
    (repo / "ansible").mkdir(parents=True)
    (repo / "ansible/session-title-prompt.txt").write_text("Prompt")
    target = tmp_path / "home/.claude/settings.json"
    target.parent.mkdir(parents=True)
    target.write_text("not json")

    with pytest.raises(ValueError, match="invalid JSON; refusing to overwrite"):
        module.render(
            repo=repo,
            home=tmp_path / "home",
            hostname="pod042",
            data=_data(),
            secrets={"CLI_PROXY_API_KEY": "proxy"},
        )
