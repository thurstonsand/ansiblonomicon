import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import tomlkit
from tomlkit.exceptions import ParseError

ROOT = Path(__file__).parents[1]


def _module() -> ModuleType:
    path = ROOT / "bootstrap/capabilities/agent-harness/configuration/codex.py"
    spec = importlib.util.spec_from_file_location("agent_configuration_codex", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _data() -> dict[str, object]:
    return {
        "models": {"openai": {"gpt_astra": {"version": "declared-astra"}}},
        "developDir": "Code Garden",
        "aigEnabled": False,
    }


def test_render_is_additive_and_preserves_live_model_comments_and_app_tables(
    tmp_path: Path,
) -> None:
    module = _module()
    home = tmp_path / "Person Home"
    target = home / ".codex/config.toml"
    target.parent.mkdir(parents=True)
    target.write_text(
        '# keep this comment\nmodel = "live-selection"\nforeign = "state"\n\n'
        "[features]\ncustom_future_flag = true\n\n"
        "[apps.generated]\nmarketplace_timestamp = 42\n"
    )
    (home / ".terminal-bg").write_text("light\n")

    rendered = module.render(
        repo=tmp_path / "unused",
        home=home,
        hostname="Thurstons-MacBook-Pro",
        data=_data(),
        secrets={},
    )[".codex/config.toml"]
    parsed = tomlkit.parse(rendered)

    assert rendered.startswith("# keep this comment\n")
    assert parsed["model"] == "live-selection"
    assert parsed["foreign"] == "state"
    assert parsed["features"]["custom_future_flag"] is True
    assert parsed["features"]["unified_exec"] is True
    assert parsed["apps"]["generated"]["marketplace_timestamp"] == 42
    assert parsed["tui"]["theme"] == "gruvbox-light"
    assert str(home / "Code Garden/ansiblonomicon") in parsed["projects"]
    assert ".codex/AGENTS.md" not in module.render(
        repo=tmp_path, home=home, hostname="x", data=_data(), secrets={}
    )


def test_fresh_home_uses_declared_model_and_pod042_trust(tmp_path: Path) -> None:
    module = _module()
    home = tmp_path / "home"
    rendered = module.render(
        repo=tmp_path,
        home=home,
        hostname="pod042",
        data=_data(),
        secrets={},
    )[".codex/config.toml"]
    parsed = tomlkit.parse(rendered)
    assert parsed["model"] == "declared-astra"
    assert parsed["projects"][str(home)]["trust_level"] == "trusted"


def test_work_host_preserves_old_exclusion(tmp_path: Path) -> None:
    assert (
        _module().render(
            repo=tmp_path,
            home=tmp_path / "home",
            hostname="ML-DFC6YK6VJQ",
            data=_data(),
            secrets={"ANTHROPIC_AUTH_TOKEN": "only-work-secret"},
        )
        == {}
    )


def test_absolute_develop_directory_is_not_prefixed_with_home(tmp_path: Path) -> None:
    module = _module()
    values = _data()
    values["developDir"] = "/srv/code"
    parsed = tomlkit.parse(
        module.render(
            repo=tmp_path,
            home=tmp_path / "home",
            hostname="pod042",
            data=values,
            secrets={},
        )[".codex/config.toml"]
    )
    assert "/srv/code/ansiblonomicon" in parsed["projects"]


def test_invalid_live_toml_is_refused(tmp_path: Path) -> None:
    module = _module()
    home = tmp_path / "home"
    target = home / ".codex/config.toml"
    target.parent.mkdir(parents=True)
    target.write_text("invalid = [")
    with pytest.raises(ParseError):
        module.render(
            repo=tmp_path, home=home, hostname="pod042", data=_data(), secrets={}
        )
