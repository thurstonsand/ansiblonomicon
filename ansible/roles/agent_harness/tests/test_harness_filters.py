"""Tests for agent_harness filter plugins."""

# pyright: reportPrivateUsage=false
from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

from harness_filters import (
    _check_standalone_plugin,
    _discover_commands_in_plugin,
    _discover_skills_in_plugin,
    _find_plugin_in_marketplace,
    _get_command_source_path,
    _get_commands_paths,
    _get_skill_source_path,
    _get_skills_paths,
    _load_plugin_json,
    _resolve_plugin_from_local,
    _resolve_plugin_from_repo,
    agent_harness_build_plugin_resources,
    agent_harness_get_git_sources,
)
import pytest

# Type aliases for fixture return types
WriteMarketplace = Callable[[dict[str, Any]], None]
WritePluginJson = Callable[[dict[str, Any], str], Path]
CreateSkill = Callable[[str], Path]
CreateCommand = Callable[[str], Path]


@pytest.fixture
def claude_plugin_dir(tmp_path: Path) -> Path:
    """Create .claude-plugin directory and return its path."""
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    return plugin_dir


@pytest.fixture
def write_marketplace(claude_plugin_dir: Path) -> WriteMarketplace:
    """Return a function to write marketplace.json with given data."""

    def _write(data: dict[str, Any]) -> None:
        (claude_plugin_dir / "marketplace.json").write_text(json.dumps(data))

    return _write


@pytest.fixture
def write_plugin_json(tmp_path: Path) -> WritePluginJson:
    """Return a function to write plugin.json at a given path."""

    def _write(data: dict[str, Any], subpath: str = ".") -> Path:
        plugin_path = tmp_path / subpath / ".claude-plugin"
        plugin_path.mkdir(parents=True, exist_ok=True)
        (plugin_path / "plugin.json").write_text(json.dumps(data))
        return tmp_path / subpath

    return _write


@pytest.fixture
def create_skill(tmp_path: Path) -> CreateSkill:
    """Return a function to create a SKILL.md at a given path."""

    def _create(subpath: str) -> Path:
        skill_path = tmp_path / subpath
        skill_path.mkdir(parents=True, exist_ok=True)
        (skill_path / "SKILL.md").write_text("# Skill")
        return skill_path

    return _create


@pytest.fixture
def create_command(tmp_path: Path) -> CreateCommand:
    """Return a function to create a command .md file at a given path."""

    def _create(subpath: str) -> Path:
        cmd_path = tmp_path / subpath
        cmd_path.parent.mkdir(parents=True, exist_ok=True)
        cmd_path.write_text("# Command")
        return cmd_path

    return _create


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """Create and return cache directory for git repos."""
    cache = tmp_path / "cache"
    cache.mkdir()
    return cache


@pytest.fixture
def repo_path(cache_dir: Path) -> Path:
    """Create a mock repo in cache and return its path."""
    repo = cache_dir / "owner--repo"
    repo.mkdir()
    return repo


# =============================================================================
# Tests for _get_skills_paths
# =============================================================================


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({}, ["skills"]),
        ({"skills": None}, ["skills"]),
        ({"skills": "custom"}, ["custom"]),
        ({"skills": "./custom"}, ["custom"]),
        ({"skills": ["a", "b"]}, ["a", "b"]),
        ({"skills": ["./a", "./b"]}, ["a", "b"]),
    ],
    ids=[
        "empty-config",
        "explicit-none",
        "string",
        "string-with-prefix",
        "list",
        "list-with-prefix",
    ],
)
@pytest.mark.unit
def test_get_skills_paths(config: dict[str, Any], expected: list[str]) -> None:
    assert _get_skills_paths(config) == expected


# =============================================================================
# Tests for _get_commands_paths
# =============================================================================


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({}, ["commands"]),
        ({"commands": None}, ["commands"]),
        ({"commands": "custom"}, ["custom"]),
        ({"commands": "./custom"}, ["custom"]),
        ({"commands": ["a", "b"]}, ["a", "b"]),
        ({"commands": ["./a", "./b"]}, ["a", "b"]),
    ],
    ids=[
        "empty-config",
        "explicit-none",
        "string",
        "string-with-prefix",
        "list",
        "list-with-prefix",
    ],
)
@pytest.mark.unit
def test_get_commands_paths(config: dict[str, Any], expected: list[str]) -> None:
    assert _get_commands_paths(config) == expected


# =============================================================================
# Tests for _load_plugin_json
# =============================================================================


@pytest.mark.unit
def test_load_plugin_json_missing(tmp_path: Path) -> None:
    assert _load_plugin_json(tmp_path) is None


@pytest.mark.unit
def test_load_plugin_json_invalid(claude_plugin_dir: Path, tmp_path: Path) -> None:
    (claude_plugin_dir / "plugin.json").write_text("not valid json")
    assert _load_plugin_json(tmp_path) is None


@pytest.mark.unit
def test_load_plugin_json_valid(claude_plugin_dir: Path, tmp_path: Path) -> None:
    config = {"name": "test-plugin", "skills": ["custom-skills"]}
    (claude_plugin_dir / "plugin.json").write_text(json.dumps(config))
    assert _load_plugin_json(tmp_path) == config


# =============================================================================
# Tests for _find_plugin_in_marketplace
# =============================================================================


@pytest.mark.unit
def test_find_plugin_in_marketplace_no_file(tmp_path: Path) -> None:
    assert _find_plugin_in_marketplace(tmp_path, "any-plugin") is None


@pytest.mark.unit
def test_find_plugin_in_marketplace_invalid_json(
    claude_plugin_dir: Path, tmp_path: Path
) -> None:
    (claude_plugin_dir / "marketplace.json").write_text("invalid")
    assert _find_plugin_in_marketplace(tmp_path, "any-plugin") is None


@pytest.mark.unit
def test_find_plugin_in_marketplace_not_found(
    write_marketplace: WriteMarketplace, tmp_path: Path
) -> None:
    write_marketplace({"plugins": [{"name": "other-plugin", "source": "./other"}]})
    assert _find_plugin_in_marketplace(tmp_path, "missing-plugin") is None


@pytest.mark.unit
def test_find_plugin_in_marketplace_string_source(
    write_marketplace: WriteMarketplace, tmp_path: Path
) -> None:
    write_marketplace(
        {"plugins": [{"name": "my-plugin", "source": "./plugins/my-plugin"}]}
    )
    result = _find_plugin_in_marketplace(tmp_path, "my-plugin")
    assert result is not None
    assert result.name == "my-plugin"
    assert result.source_path == "plugins/my-plugin"
    assert result.skills_paths == ["skills"]
    assert result.commands_paths == ["commands"]


@pytest.mark.parametrize(
    ("source", "plugin_root", "expected_path"),
    [
        ("my-plugin", "plugins", "plugins/my-plugin"),
        ("./explicit/path", "plugins", "explicit/path"),
        ("/absolute/path", "plugins", "absolute/path"),
    ],
    ids=["relative-with-root", "explicit-path-ignores-root", "absolute-ignores-root"],
)
@pytest.mark.unit
def test_find_plugin_in_marketplace_plugin_root(
    write_marketplace: WriteMarketplace,
    tmp_path: Path,
    source: str,
    plugin_root: str,
    expected_path: str,
) -> None:
    write_marketplace(
        {
            "metadata": {"pluginRoot": plugin_root},
            "plugins": [{"name": "my-plugin", "source": source}],
        }
    )
    result = _find_plugin_in_marketplace(tmp_path, "my-plugin")
    assert result is not None
    assert result.source_path == expected_path


@pytest.mark.parametrize(
    "external_source",
    [
        {"source": "github", "repo": "owner/repo"},
        {"source": "url", "url": "https://example.com/plugin.git"},
    ],
    ids=["github", "url"],
)
@pytest.mark.unit
def test_find_plugin_in_marketplace_skips_external_source(
    write_marketplace: WriteMarketplace, tmp_path: Path, external_source: dict[str, str]
) -> None:
    write_marketplace(
        {"plugins": [{"name": "external-plugin", "source": external_source}]}
    )
    assert _find_plugin_in_marketplace(tmp_path, "external-plugin") is None


@pytest.mark.unit
def test_find_plugin_in_marketplace_strict_true_merges_plugin_json(
    write_marketplace: WriteMarketplace,
    write_plugin_json: WritePluginJson,
    tmp_path: Path,
) -> None:
    write_marketplace(
        {"plugins": [{"name": "my-plugin", "source": "./my-plugin", "strict": True}]}
    )
    write_plugin_json(
        {"name": "my-plugin", "skills": "custom", "commands": "cmds"}, "my-plugin"
    )

    result = _find_plugin_in_marketplace(tmp_path, "my-plugin")
    assert result is not None
    assert result.skills_paths == ["custom"]
    assert result.commands_paths == ["cmds"]


@pytest.mark.unit
def test_find_plugin_in_marketplace_strict_true_fallback_to_marketplace(
    write_marketplace: WriteMarketplace, tmp_path: Path
) -> None:
    write_marketplace(
        {
            "plugins": [
                {
                    "name": "my-plugin",
                    "source": "./my-plugin",
                    "skills": ["from-marketplace"],
                }
            ]
        }
    )
    (tmp_path / "my-plugin").mkdir()

    result = _find_plugin_in_marketplace(tmp_path, "my-plugin")
    assert result is not None
    assert result.skills_paths == ["from-marketplace"]


@pytest.mark.unit
def test_find_plugin_in_marketplace_strict_false_ignores_plugin_json(
    write_marketplace: WriteMarketplace,
    write_plugin_json: WritePluginJson,
    tmp_path: Path,
) -> None:
    write_marketplace(
        {
            "plugins": [
                {
                    "name": "simple-plugin",
                    "source": "./simple",
                    "strict": False,
                    "skills": "inline-skills",
                }
            ]
        }
    )
    write_plugin_json({"skills": "should-be-ignored"}, "simple")

    result = _find_plugin_in_marketplace(tmp_path, "simple-plugin")
    assert result is not None
    assert result.skills_paths == ["inline-skills"]


@pytest.mark.unit
def test_find_plugin_in_marketplace_merge_prefers_marketplace(
    write_marketplace: WriteMarketplace,
    write_plugin_json: WritePluginJson,
    tmp_path: Path,
) -> None:
    write_marketplace(
        {
            "plugins": [
                {
                    "name": "my-plugin",
                    "source": "./my-plugin",
                    "skills": ["marketplace-override"],
                }
            ]
        }
    )
    write_plugin_json({"name": "my-plugin", "skills": ["plugin-default"]}, "my-plugin")

    result = _find_plugin_in_marketplace(tmp_path, "my-plugin")
    assert result is not None
    assert result.skills_paths == ["marketplace-override"]


# =============================================================================
# Tests for _check_standalone_plugin
# =============================================================================


@pytest.mark.unit
def test_check_standalone_plugin_no_plugin_json(tmp_path: Path) -> None:
    assert _check_standalone_plugin(tmp_path, "any") is None


@pytest.mark.unit
def test_check_standalone_plugin_name_mismatch(
    write_plugin_json: WritePluginJson, tmp_path: Path
) -> None:
    write_plugin_json({"name": "actual-name"}, ".")
    assert _check_standalone_plugin(tmp_path, "different-name") is None


@pytest.mark.parametrize(
    ("plugin_config", "expected_skills_paths", "expected_commands_paths"),
    [
        ({"name": "my-plugin"}, ["skills"], ["commands"]),
        ({"name": "my-plugin", "skills": ["a", "b"]}, ["a", "b"], ["commands"]),
        ({"name": "my-plugin", "commands": "cmds"}, ["skills"], ["cmds"]),
    ],
    ids=["default-paths", "custom-skills", "custom-commands"],
)
@pytest.mark.unit
def test_check_standalone_plugin_found(
    write_plugin_json: WritePluginJson,
    tmp_path: Path,
    plugin_config: dict[str, Any],
    expected_skills_paths: list[str],
    expected_commands_paths: list[str],
) -> None:
    write_plugin_json(plugin_config, ".")
    result = _check_standalone_plugin(tmp_path, "my-plugin")
    assert result is not None
    assert result.name == "my-plugin"
    assert result.source_path == "."
    assert result.skills_paths == expected_skills_paths
    assert result.commands_paths == expected_commands_paths


# =============================================================================
# Tests for _discover_skills_in_plugin
# =============================================================================


@pytest.mark.unit
def test_discover_skills_in_plugin_empty(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir()
    result = _discover_skills_in_plugin(tmp_path, ["skills"], "my-plugin")
    assert result == []


@pytest.mark.unit
def test_discover_skills_in_plugin_finds_skills(
    tmp_path: Path, create_skill: CreateSkill
) -> None:
    create_skill("skills/skill-a")
    create_skill("skills/skill-b")
    result = _discover_skills_in_plugin(tmp_path, ["skills"], "my-plugin")
    assert sorted(result) == ["skill-a", "skill-b"]


@pytest.mark.unit
def test_discover_skills_in_plugin_multiple_paths(
    tmp_path: Path, create_skill: CreateSkill
) -> None:
    create_skill("skills/skill-a")
    create_skill("other/skill-b")
    result = _discover_skills_in_plugin(tmp_path, ["skills", "other"], "my-plugin")
    assert sorted(result) == ["skill-a", "skill-b"]


@pytest.mark.unit
def test_discover_skills_in_plugin_root_skill(tmp_path: Path) -> None:
    (tmp_path / "SKILL.md").write_text("# Root skill")
    result = _discover_skills_in_plugin(tmp_path, ["skills"], "my-plugin")
    assert result == ["my-plugin"]


@pytest.mark.unit
def test_discover_skills_in_plugin_root_and_nested(
    tmp_path: Path, create_skill: CreateSkill
) -> None:
    (tmp_path / "SKILL.md").write_text("# Root skill")
    create_skill("skills/nested-skill")
    result = _discover_skills_in_plugin(tmp_path, ["skills"], "my-plugin")
    assert len(result) == 2
    assert "my-plugin" in result
    assert "nested-skill" in result


@pytest.mark.unit
def test_discover_skills_in_plugin_ignores_non_skill_dirs(tmp_path: Path) -> None:
    (tmp_path / "skills" / "not-a-skill").mkdir(parents=True)
    (tmp_path / "skills" / "not-a-skill" / "README.md").write_text("# Not a skill")
    result = _discover_skills_in_plugin(tmp_path, ["skills"], "my-plugin")
    assert result == []


# =============================================================================
# Tests for _discover_commands_in_plugin
# =============================================================================


@pytest.mark.unit
def test_discover_commands_in_plugin_empty(tmp_path: Path) -> None:
    (tmp_path / "commands").mkdir()
    result = _discover_commands_in_plugin(tmp_path, ["commands"])
    assert result == []


@pytest.mark.unit
def test_discover_commands_in_plugin_finds_commands(
    tmp_path: Path, create_command: CreateCommand
) -> None:
    create_command("commands/cmd-a.md")
    create_command("commands/cmd-b.md")
    result = _discover_commands_in_plugin(tmp_path, ["commands"])
    assert sorted(result) == ["cmd-a", "cmd-b"]


@pytest.mark.unit
def test_discover_commands_in_plugin_multiple_paths(
    tmp_path: Path, create_command: CreateCommand
) -> None:
    create_command("commands/cmd-a.md")
    create_command("other/cmd-b.md")
    result = _discover_commands_in_plugin(tmp_path, ["commands", "other"])
    assert sorted(result) == ["cmd-a", "cmd-b"]


@pytest.mark.unit
def test_discover_commands_in_plugin_ignores_non_md(tmp_path: Path) -> None:
    (tmp_path / "commands").mkdir()
    (tmp_path / "commands" / "script.sh").write_text("#!/bin/bash")
    (tmp_path / "commands" / "config.json").write_text("{}")
    result = _discover_commands_in_plugin(tmp_path, ["commands"])
    assert result == []


# =============================================================================
# Tests for _get_skill_source_path
# =============================================================================


@pytest.mark.unit
def test_get_skill_source_path_found(
    tmp_path: Path, create_skill: CreateSkill
) -> None:
    create_skill("skills/my-skill")
    result = _get_skill_source_path(tmp_path, "my-skill", ["skills"], "my-plugin")
    assert result == str(tmp_path / "skills" / "my-skill")


@pytest.mark.unit
def test_get_skill_source_path_root_skill(tmp_path: Path) -> None:
    (tmp_path / "SKILL.md").write_text("# Root skill")
    result = _get_skill_source_path(tmp_path, "my-plugin", ["skills"], "my-plugin")
    assert result == str(tmp_path)


@pytest.mark.unit
def test_get_skill_source_path_not_found(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir()
    result = _get_skill_source_path(tmp_path, "missing", ["skills"], "my-plugin")
    assert result is None


# =============================================================================
# Tests for _get_command_source_path
# =============================================================================


@pytest.mark.unit
def test_get_command_source_path_found(
    tmp_path: Path, create_command: CreateCommand
) -> None:
    create_command("commands/my-cmd.md")
    result = _get_command_source_path(tmp_path, "my-cmd", ["commands"])
    assert result == str(tmp_path / "commands" / "my-cmd.md")


@pytest.mark.unit
def test_get_command_source_path_not_found(tmp_path: Path) -> None:
    (tmp_path / "commands").mkdir()
    result = _get_command_source_path(tmp_path, "missing", ["commands"])
    assert result is None


# =============================================================================
# Tests for _resolve_plugin_from_repo
# =============================================================================


@pytest.mark.unit
def test_resolve_plugin_from_repo_marketplace(
    repo_path: Path, write_marketplace: WriteMarketplace
) -> None:
    # write_marketplace uses tmp_path, so create marketplace in repo_path manually
    plugin_dir = repo_path / ".claude-plugin"
    plugin_dir.mkdir()
    marketplace = {"plugins": [{"name": "my-plugin", "source": "./plugins/my-plugin"}]}
    (plugin_dir / "marketplace.json").write_text(json.dumps(marketplace))

    config, plugin_path, exclude_skills, exclude_commands = _resolve_plugin_from_repo(
        repo_path, "my-plugin"
    )
    assert config is not None
    assert config.name == "my-plugin"
    assert plugin_path == repo_path / "plugins" / "my-plugin"
    assert exclude_skills == []
    assert exclude_commands == []


@pytest.mark.unit
def test_resolve_plugin_from_repo_standalone(
    repo_path: Path, write_plugin_json: WritePluginJson
) -> None:
    plugin_dir = repo_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps({"name": "standalone"}))

    config, plugin_path, exclude_skills, _ = _resolve_plugin_from_repo(
        repo_path, "standalone"
    )
    assert config is not None
    assert config.name == "standalone"
    assert plugin_path == repo_path
    assert exclude_skills == []


@pytest.mark.unit
def test_resolve_plugin_from_repo_explicit_path(repo_path: Path) -> None:
    (repo_path / "custom" / "location").mkdir(parents=True)

    config, resolved_path, _, _ = _resolve_plugin_from_repo(
        repo_path, {"name": "explicit", "path": "custom/location"}
    )
    assert config is not None
    assert config.name == "explicit"
    assert resolved_path == repo_path / "custom" / "location"


@pytest.mark.unit
def test_resolve_plugin_from_repo_with_exclusions(repo_path: Path) -> None:
    plugin_dir = repo_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps({"name": "my-plugin"}))

    config, _, exclude_skills, exclude_commands = _resolve_plugin_from_repo(
        repo_path,
        {
            "name": "my-plugin",
            "exclude_skills": ["unwanted-skill"],
            "exclude_commands": ["unwanted-cmd"],
        },
    )
    assert config is not None
    assert exclude_skills == ["unwanted-skill"]
    assert exclude_commands == ["unwanted-cmd"]


@pytest.mark.unit
def test_resolve_plugin_from_repo_not_found(repo_path: Path) -> None:
    config, plugin_path, _, _ = _resolve_plugin_from_repo(repo_path, "nonexistent")
    assert config is None
    assert plugin_path is None


# =============================================================================
# Tests for _resolve_plugin_from_local
# =============================================================================


@pytest.mark.unit
def test_resolve_plugin_from_local_explicit_path(tmp_path: Path) -> None:
    (tmp_path / "my-plugins" / "custom").mkdir(parents=True)

    config, resolved_path, _, _ = _resolve_plugin_from_local(
        str(tmp_path / "my-plugins"), {"name": "custom", "path": "custom"}
    )
    assert config is not None
    assert config.name == "custom"
    assert resolved_path == tmp_path / "my-plugins" / "custom"


@pytest.mark.unit
def test_resolve_plugin_from_local_with_exclusions(tmp_path: Path) -> None:
    (tmp_path / "plugins" / "my-plugin").mkdir(parents=True)

    config, _, exclude_skills, exclude_commands = _resolve_plugin_from_local(
        str(tmp_path),
        {
            "name": "my-plugin",
            "exclude_skills": ["skip-skill"],
            "exclude_commands": ["skip-cmd"],
        },
    )
    assert config is not None
    assert exclude_skills == ["skip-skill"]
    assert exclude_commands == ["skip-cmd"]


# =============================================================================
# Tests for agent_harness_get_git_sources
# =============================================================================


@pytest.mark.unit
def test_agent_harness_get_git_sources_empty() -> None:
    assert agent_harness_get_git_sources([]) == []


@pytest.mark.unit
def test_agent_harness_get_git_sources_filters_to_git_only() -> None:
    sources: list[Any] = [
        {"repo": "owner/repo1", "plugins": ["a"]},
        {"local": "/path", "plugins": ["b"]},
        {"repo": "owner/repo2", "plugins": ["c"]},
    ]
    result = agent_harness_get_git_sources(sources)
    assert len(result) == 2
    assert result[0]["repo"] == "owner/repo1"
    assert result[1]["repo"] == "owner/repo2"


@pytest.mark.unit
def test_agent_harness_get_git_sources_preserves_fields() -> None:
    sources: list[Any] = [{"repo": "owner/repo", "pull": True, "plugins": ["x", "y"]}]
    result = agent_harness_get_git_sources(sources)
    assert result[0]["pull"] is True
    assert result[0]["plugins"] == ["x", "y"]


# =============================================================================
# Tests for agent_harness_build_plugin_resources
# =============================================================================


@pytest.mark.unit
def test_agent_harness_build_plugin_resources_empty(cache_dir: Path) -> None:
    result = agent_harness_build_plugin_resources([], str(cache_dir))
    assert result == {"skills": [], "commands": []}


# --- Git source tests ---


@pytest.mark.unit
def test_agent_harness_build_plugin_resources_git_discovers_skills(
    repo_path: Path, cache_dir: Path, create_skill: CreateSkill
) -> None:
    # Setup marketplace
    plugin_dir = repo_path / ".claude-plugin"
    plugin_dir.mkdir()
    marketplace = {"plugins": [{"name": "my-plugin", "source": "./plugins/my-plugin"}]}
    (plugin_dir / "marketplace.json").write_text(json.dumps(marketplace))

    # Create skills in the plugin
    skill_a = repo_path / "plugins" / "my-plugin" / "skills" / "skill-a"
    skill_a.mkdir(parents=True)
    (skill_a / "SKILL.md").write_text("# Skill A")

    skill_b = repo_path / "plugins" / "my-plugin" / "skills" / "skill-b"
    skill_b.mkdir(parents=True)
    (skill_b / "SKILL.md").write_text("# Skill B")

    sources: list[Any] = [{"repo": "owner/repo", "plugins": ["my-plugin"]}]
    result = agent_harness_build_plugin_resources(sources, str(cache_dir))

    assert len(result["skills"]) == 2
    names = sorted(s["name"] for s in result["skills"])
    assert names == ["skill-a", "skill-b"]
    assert all(s["origin"] == "owner/repo" for s in result["skills"])


@pytest.mark.unit
def test_agent_harness_build_plugin_resources_git_discovers_commands(
    repo_path: Path, cache_dir: Path
) -> None:
    # Setup standalone plugin
    plugin_dir = repo_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps({"name": "my-plugin"}))

    # Create commands
    cmd_dir = repo_path / "commands"
    cmd_dir.mkdir()
    (cmd_dir / "cmd-a.md").write_text("# Command A")
    (cmd_dir / "cmd-b.md").write_text("# Command B")

    sources: list[Any] = [{"repo": "owner/repo", "plugins": ["my-plugin"]}]
    result = agent_harness_build_plugin_resources(sources, str(cache_dir))

    assert len(result["commands"]) == 2
    names = sorted(c["name"] for c in result["commands"])
    assert names == ["cmd-a", "cmd-b"]


@pytest.mark.unit
def test_agent_harness_build_plugin_resources_git_with_exclusions(
    repo_path: Path, cache_dir: Path
) -> None:
    # Setup standalone plugin
    plugin_dir = repo_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps({"name": "my-plugin"}))

    # Create skills
    for name in ["keep-skill", "skip-skill"]:
        skill_dir = repo_path / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {name}")

    # Create commands
    cmd_dir = repo_path / "commands"
    cmd_dir.mkdir()
    (cmd_dir / "keep-cmd.md").write_text("# Keep")
    (cmd_dir / "skip-cmd.md").write_text("# Skip")

    sources: list[Any] = [
        {
            "repo": "owner/repo",
            "plugins": [
                {
                    "name": "my-plugin",
                    "exclude_skills": ["skip-skill"],
                    "exclude_commands": ["skip-cmd"],
                }
            ],
        }
    ]
    result = agent_harness_build_plugin_resources(sources, str(cache_dir))

    assert len(result["skills"]) == 1
    assert result["skills"][0]["name"] == "keep-skill"
    assert len(result["commands"]) == 1
    assert result["commands"][0]["name"] == "keep-cmd"


@pytest.mark.unit
def test_agent_harness_build_plugin_resources_git_root_skill(
    repo_path: Path, cache_dir: Path
) -> None:
    # Setup standalone plugin where root is the skill
    plugin_dir = repo_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps({"name": "single-skill"}))
    (repo_path / "SKILL.md").write_text("# The plugin is the skill")

    sources: list[Any] = [{"repo": "owner/repo", "plugins": ["single-skill"]}]
    result = agent_harness_build_plugin_resources(sources, str(cache_dir))

    assert len(result["skills"]) == 1
    assert result["skills"][0]["source"] == str(repo_path)


@pytest.mark.unit
def test_agent_harness_build_plugin_resources_git_explicit_path(
    repo_path: Path, cache_dir: Path
) -> None:
    # Create plugin at custom path
    custom_plugin = repo_path / "custom" / "path"
    custom_plugin.mkdir(parents=True)
    skill_dir = custom_plugin / "skills" / "custom-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Custom")

    sources: list[Any] = [
        {"repo": "owner/repo", "plugins": [{"name": "custom", "path": "custom/path"}]}
    ]
    result = agent_harness_build_plugin_resources(sources, str(cache_dir))

    assert len(result["skills"]) == 1
    assert result["skills"][0]["name"] == "custom-skill"


# --- Local source tests ---


@pytest.mark.unit
def test_agent_harness_build_plugin_resources_local_discovers_skills(
    tmp_path: Path, cache_dir: Path
) -> None:
    # Create local plugin structure
    local_path = tmp_path / "local"
    plugin_path = local_path / "plugins" / "my-plugin"
    skill_dir = plugin_path / "skills" / "local-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Local Skill")

    sources: list[Any] = [{"local": str(local_path), "plugins": ["my-plugin"]}]
    result = agent_harness_build_plugin_resources(sources, str(cache_dir))

    assert len(result["skills"]) == 1
    assert result["skills"][0]["name"] == "local-skill"
    assert result["skills"][0]["origin"] == "local"


@pytest.mark.unit
def test_agent_harness_build_plugin_resources_local_discovers_commands(
    tmp_path: Path, cache_dir: Path
) -> None:
    # Create local plugin structure
    local_path = tmp_path / "local"
    plugin_path = local_path / "plugins" / "my-plugin"
    cmd_dir = plugin_path / "commands"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "local-cmd.md").write_text("# Local Command")

    sources: list[Any] = [{"local": str(local_path), "plugins": ["my-plugin"]}]
    result = agent_harness_build_plugin_resources(sources, str(cache_dir))

    assert len(result["commands"]) == 1
    assert result["commands"][0]["name"] == "local-cmd"
    assert result["commands"][0]["origin"] == "local"


@pytest.mark.unit
def test_agent_harness_build_plugin_resources_local_with_exclusions(
    tmp_path: Path, cache_dir: Path
) -> None:
    # Create local plugin structure
    local_path = tmp_path / "local"
    plugin_path = local_path / "plugins" / "my-plugin"

    for name in ["keep", "skip"]:
        skill_dir = plugin_path / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {name}")

    sources: list[Any] = [
        {
            "local": str(local_path),
            "plugins": [{"name": "my-plugin", "exclude_skills": ["skip"]}],
        }
    ]
    result = agent_harness_build_plugin_resources(sources, str(cache_dir))

    assert len(result["skills"]) == 1
    assert result["skills"][0]["name"] == "keep"


# --- Integration tests ---


@pytest.mark.unit
def test_agent_harness_build_plugin_resources_multiple_sources(
    tmp_path: Path, cache_dir: Path
) -> None:
    # Git source
    repo_path = cache_dir / "owner--repo"
    plugin_dir = repo_path / ".claude-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps({"name": "git-plugin"}))
    git_skill = repo_path / "skills" / "git-skill"
    git_skill.mkdir(parents=True)
    (git_skill / "SKILL.md").write_text("# Git Skill")

    # Local source
    local_path = tmp_path / "local"
    local_plugin = local_path / "plugins" / "local-plugin"
    local_skill = local_plugin / "skills" / "local-skill"
    local_skill.mkdir(parents=True)
    (local_skill / "SKILL.md").write_text("# Local Skill")

    sources: list[Any] = [
        {"repo": "owner/repo", "plugins": ["git-plugin"]},
        {"local": str(local_path), "plugins": ["local-plugin"]},
    ]
    result = agent_harness_build_plugin_resources(sources, str(cache_dir))

    assert len(result["skills"]) == 2
    names = sorted(s["name"] for s in result["skills"])
    assert names == ["git-skill", "local-skill"]


@pytest.mark.unit
def test_agent_harness_build_plugin_resources_mixed_skills_and_commands(
    tmp_path: Path, cache_dir: Path
) -> None:
    # Create local plugin with both skills and commands
    local_path = tmp_path / "local"
    plugin_path = local_path / "plugins" / "mixed-plugin"

    skill_dir = plugin_path / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Skill")

    cmd_dir = plugin_path / "commands"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "my-cmd.md").write_text("# Command")

    sources: list[Any] = [{"local": str(local_path), "plugins": ["mixed-plugin"]}]
    result = agent_harness_build_plugin_resources(sources, str(cache_dir))

    assert len(result["skills"]) == 1
    assert result["skills"][0]["name"] == "my-skill"
    assert len(result["commands"]) == 1
    assert result["commands"][0]["name"] == "my-cmd"


@pytest.mark.unit
def test_agent_harness_build_plugin_resources_unresolvable_skipped(
    cache_dir: Path,
) -> None:
    sources: list[Any] = [{"repo": "owner/repo", "plugins": ["nonexistent"]}]
    result = agent_harness_build_plugin_resources(sources, str(cache_dir))
    assert result == {"skills": [], "commands": []}


@pytest.mark.unit
def test_agent_harness_build_plugin_resources_multiple_plugins_same_source(
    repo_path: Path, cache_dir: Path
) -> None:
    # Setup marketplace with multiple plugins
    plugin_dir = repo_path / ".claude-plugin"
    plugin_dir.mkdir()
    marketplace = {
        "plugins": [
            {"name": "plugin-a", "source": "./plugins/plugin-a"},
            {"name": "plugin-b", "source": "./plugins/plugin-b"},
        ]
    }
    (plugin_dir / "marketplace.json").write_text(json.dumps(marketplace))

    # Create skills in each plugin
    for plugin_name in ["plugin-a", "plugin-b"]:
        skill_dir = repo_path / "plugins" / plugin_name / "skills" / f"{plugin_name}-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {plugin_name} skill")

    sources: list[Any] = [
        {"repo": "owner/repo", "plugins": ["plugin-a", "plugin-b"]}
    ]
    result = agent_harness_build_plugin_resources(sources, str(cache_dir))

    assert len(result["skills"]) == 2
    names = sorted(s["name"] for s in result["skills"])
    assert names == ["plugin-a-skill", "plugin-b-skill"]
