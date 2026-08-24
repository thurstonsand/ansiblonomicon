"""Tests for agent_harness filter plugins."""

# pyright: reportPrivateUsage=false
from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

from harness_filters import (
    _build_model_alias_map,
    _repo_to_cache_name,
    agent_harness_build_plugin_resources,
    agent_harness_filter_resources,
    agent_harness_repo_to_cache_name,
    agent_harness_transform_skill,
    agent_harness_transform_skill_content,
)
import pytest

MakeSkill = Callable[[Path], Path]
MakeAgent = Callable[[Path], Path]


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """Create and return the cache directory for git repos."""
    cache = tmp_path / "cache"
    cache.mkdir()
    return cache


@pytest.fixture
def repo_path(cache_dir: Path) -> Path:
    """Create a checkout of owner/repo in the cache and return its path."""
    repo = cache_dir / "owner--repo"
    repo.mkdir()
    return repo


@pytest.fixture
def local_root(tmp_path: Path) -> Path:
    """Create and return the root of a local (in-repo) source."""
    local = tmp_path / "agents"
    local.mkdir()
    return local


@pytest.fixture
def make_skill() -> MakeSkill:
    """Return a function that turns a directory into a skill."""

    def _make(directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(f"---\nname: {directory.name}\n---\n")
        return directory

    return _make


@pytest.fixture
def make_agent() -> MakeAgent:
    """Return a function that writes an agent markdown file."""

    def _make(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nname: {path.stem}\n---\n")
        return path

    return _make


def write_manifest(plugin_root: Path, manifest: dict[str, Any]) -> Path:
    """Write .claude-plugin/plugin.json under a plugin root."""
    manifest_dir = plugin_root / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "plugin.json").write_text(json.dumps(manifest))
    return plugin_root


def write_marketplace(repo_path: Path, marketplace: dict[str, Any]) -> Path:
    """Write .claude-plugin/marketplace.json at a repo root."""
    manifest_dir = repo_path / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "marketplace.json").write_text(json.dumps(marketplace))
    return repo_path


def repo_source(plugins: list[dict[str, Any]]) -> dict[str, Any]:
    return {"repo": "owner/repo", "plugins": plugins}


def local_source(local_root: Path, plugins: list[dict[str, Any]]) -> dict[str, Any]:
    return {"local": str(local_root), "plugins": plugins}


def names(resources: list[dict[str, Any]]) -> list[str]:
    return [resource["name"] for resource in resources]


# =============================================================================
# Manifest fallback: marketplace.json
# =============================================================================


@pytest.mark.unit
def test_marketplace_entry_locates_the_plugin_and_its_skills(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_marketplace(
        repo_path, {"plugins": [{"name": "my-plugin", "source": "./plugins/mine"}]}
    )
    plugin_root = repo_path / "plugins" / "mine"
    write_manifest(plugin_root, {"name": "my-plugin"})
    make_skill(plugin_root / "skills" / "alpha")
    make_skill(plugin_root / "skills" / "beta")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert names(result["skills"]) == ["alpha", "beta"]
    assert result["skills"][0]["plugin_root"] == str(plugin_root)
    assert result["skills"][0]["origin"] == "owner/repo"


@pytest.mark.unit
def test_marketplace_metadata_plugin_root_prefixes_relative_sources(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_marketplace(
        repo_path,
        {
            "metadata": {"pluginRoot": "packages"},
            "plugins": [{"name": "my-plugin", "source": "mine"}],
        },
    )
    plugin_root = repo_path / "packages" / "mine"
    write_manifest(plugin_root, {"name": "my-plugin"})
    make_skill(plugin_root / "skills" / "alpha")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert result["skills"][0]["plugin_root"] == str(plugin_root)


@pytest.mark.unit
def test_strict_marketplace_entry_merges_over_plugin_json(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_marketplace(
        repo_path,
        {"plugins": [{"name": "my-plugin", "source": "./", "skills": ["curated"]}]},
    )
    write_manifest(repo_path, {"name": "my-plugin", "skills": ["everything"]})
    make_skill(repo_path / "curated" / "alpha")
    make_skill(repo_path / "everything" / "beta")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert names(result["skills"]) == ["alpha"]


@pytest.mark.unit
def test_strict_marketplace_entry_inherits_plugin_json_paths(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_marketplace(repo_path, {"plugins": [{"name": "my-plugin", "source": "./"}]})
    write_manifest(repo_path, {"name": "my-plugin", "skills": ["./nested/skills"]})
    make_skill(repo_path / "nested" / "skills" / "alpha")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert names(result["skills"]) == ["alpha"]


@pytest.mark.unit
def test_non_strict_marketplace_entry_ignores_plugin_json(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_marketplace(
        repo_path,
        {
            "plugins": [
                {
                    "name": "my-plugin",
                    "source": "./",
                    "strict": False,
                    "skills": ["./skills/only-this"],
                }
            ]
        },
    )
    write_manifest(repo_path, {"name": "my-plugin", "skills": ["./skills"]})
    make_skill(repo_path / "skills" / "only-this")
    make_skill(repo_path / "skills" / "other")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert names(result["skills"]) == ["only-this"]


@pytest.mark.unit
def test_marketplace_dict_source_falls_through_to_unresolvable(
    repo_path: Path, cache_dir: Path
) -> None:
    write_marketplace(
        repo_path,
        {"plugins": [{"name": "my-plugin", "source": {"source": "github"}}]},
    )

    with pytest.raises(ValueError, match=r"plugin my-plugin: no manifest found"):
        agent_harness_build_plugin_resources(
            [repo_source([{"name": "my-plugin"}])], str(cache_dir)
        )


# =============================================================================
# Manifest fallback: standalone plugin.json and local plugins
# =============================================================================


@pytest.mark.unit
def test_standalone_plugin_json_at_repo_root_resolves(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_manifest(repo_path, {"name": "my-plugin"})
    make_skill(repo_path / "skills" / "alpha")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert names(result["skills"]) == ["alpha"]
    assert result["skills"][0]["plugin_root"] == str(repo_path)


@pytest.mark.unit
def test_standalone_plugin_json_with_a_different_name_is_fatal(
    repo_path: Path, cache_dir: Path
) -> None:
    write_manifest(repo_path, {"name": "other-plugin"})

    with pytest.raises(ValueError, match=r"plugin my-plugin: no manifest found"):
        agent_harness_build_plugin_resources(
            [repo_source([{"name": "my-plugin"}])], str(cache_dir)
        )


@pytest.mark.unit
def test_local_plugin_resolves_under_the_source_root(
    local_root: Path, cache_dir: Path, make_skill: MakeSkill, make_agent: MakeAgent
) -> None:
    plugin_root = write_manifest(local_root / "mine", {"name": "mine"})
    make_skill(plugin_root / "skills" / "alpha")
    make_agent(plugin_root / "agents" / "helper.md")

    result = agent_harness_build_plugin_resources(
        [local_source(local_root, [{"name": "mine"}])], str(cache_dir)
    )

    assert names(result["skills"]) == ["alpha"]
    assert names(result["agents"]) == ["helper"]
    assert result["skills"][0]["origin"] == "local"
    assert result["skills"][0]["plugin_root"] == str(plugin_root)


@pytest.mark.unit
def test_local_plugin_without_a_manifest_is_fatal(
    local_root: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    make_skill(local_root / "mine" / "skills" / "alpha")

    with pytest.raises(ValueError, match=r"plugin mine: no manifest found"):
        agent_harness_build_plugin_resources(
            [local_source(local_root, [{"name": "mine"}])], str(cache_dir)
        )


# =============================================================================
# Manifest discovery rules
# =============================================================================


@pytest.mark.unit
def test_a_plugin_that_is_itself_a_skill_short_circuits_discovery(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_manifest(repo_path, {"name": "my-plugin"})
    make_skill(repo_path)
    make_skill(repo_path / "skills" / "alpha")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert names(result["skills"]) == ["my-plugin"]
    assert result["skills"][0]["source"] == str(repo_path)


@pytest.mark.unit
def test_a_manifest_path_that_is_itself_a_skill_is_one_skill(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_manifest(repo_path, {"name": "my-plugin", "skills": "./skills/alpha"})
    make_skill(repo_path / "skills" / "alpha")
    make_skill(repo_path / "skills" / "alpha" / "nested")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert names(result["skills"]) == ["alpha"]


@pytest.mark.unit
def test_discovery_ignores_directories_without_a_skill_file(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_manifest(repo_path, {"name": "my-plugin"})
    make_skill(repo_path / "skills" / "alpha")
    (repo_path / "skills" / "docs").mkdir()

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert names(result["skills"]) == ["alpha"]


@pytest.mark.unit
def test_discovery_accepts_a_templated_skill_file(
    repo_path: Path, cache_dir: Path
) -> None:
    write_manifest(repo_path, {"name": "my-plugin"})
    skill_dir = repo_path / "skills" / "alpha"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md.j2").write_text("---\nname: alpha\n---\n")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert names(result["skills"]) == ["alpha"]


@pytest.mark.unit
def test_missing_manifest_paths_are_skipped(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_manifest(repo_path, {"name": "my-plugin", "skills": ["gone", "./skills"]})
    make_skill(repo_path / "skills" / "alpha")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert names(result["skills"]) == ["alpha"]


@pytest.mark.unit
def test_agents_are_the_markdown_files_in_the_manifest_paths(
    repo_path: Path, cache_dir: Path, make_agent: MakeAgent
) -> None:
    write_manifest(repo_path, {"name": "my-plugin", "agents": ["./crew"]})
    make_agent(repo_path / "crew" / "scout.md")
    make_agent(repo_path / "crew" / "sniper.md")
    (repo_path / "crew" / "notes.txt").write_text("not an agent")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert names(result["agents"]) == ["scout", "sniper"]


# =============================================================================
# Explicit skills/agents maps
# =============================================================================


@pytest.mark.unit
def test_explicit_skills_map_resolves_against_the_repo_root(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    make_skill(repo_path / "skills" / "upstream-name")

    result = agent_harness_build_plugin_resources(
        [
            repo_source(
                [{"name": "hunk", "skills": {"deployed": "skills/upstream-name"}}]
            )
        ],
        str(cache_dir),
    )

    assert names(result["skills"]) == ["deployed"]
    assert result["skills"][0]["source"] == str(repo_path / "skills" / "upstream-name")
    assert result["skills"][0]["plugin_root"] == str(repo_path)


@pytest.mark.unit
def test_explicit_maps_need_no_manifest(
    local_root: Path, cache_dir: Path, make_skill: MakeSkill, make_agent: MakeAgent
) -> None:
    make_skill(local_root / "loose" / "alpha")
    make_agent(local_root / "loose" / "scout.md")

    result = agent_harness_build_plugin_resources(
        [
            local_source(
                local_root,
                [
                    {
                        "name": "loose",
                        "skills": {"alpha": "loose/alpha"},
                        "agents": {"scout": "loose/scout.md"},
                    }
                ],
            )
        ],
        str(cache_dir),
    )

    assert names(result["skills"]) == ["alpha"]
    assert names(result["agents"]) == ["scout"]
    assert result["skills"][0]["plugin_root"] == str(local_root)


@pytest.mark.unit
def test_without_a_manifest_the_unmapped_kind_stays_empty(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill, make_agent: MakeAgent
) -> None:
    make_skill(repo_path / "skills" / "alpha")
    make_agent(repo_path / "agents" / "scout.md")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "p", "skills": {"alpha": "skills/alpha"}}])],
        str(cache_dir),
    )

    assert names(result["skills"]) == ["alpha"]
    assert result["agents"] == []


@pytest.mark.unit
def test_explicit_skill_path_without_a_skill_file_is_fatal(
    repo_path: Path, cache_dir: Path
) -> None:
    (repo_path / "skills" / "empty").mkdir(parents=True)

    with pytest.raises(
        ValueError, match=r"skill 'deployed' at .*empty has no SKILL.md"
    ):
        agent_harness_build_plugin_resources(
            [repo_source([{"name": "p", "skills": {"deployed": "skills/empty"}}])],
            str(cache_dir),
        )


@pytest.mark.unit
def test_explicit_skill_path_that_is_missing_is_fatal(
    repo_path: Path, cache_dir: Path
) -> None:
    with pytest.raises(ValueError, match=r"skill 'deployed' at .*gone has no SKILL.md"):
        agent_harness_build_plugin_resources(
            [repo_source([{"name": "p", "skills": {"deployed": "gone"}}])],
            str(cache_dir),
        )


@pytest.mark.unit
def test_explicit_agent_path_that_is_not_markdown_is_fatal(
    repo_path: Path, cache_dir: Path
) -> None:
    (repo_path / "crew").mkdir()
    (repo_path / "crew" / "scout.txt").write_text("nope")

    with pytest.raises(ValueError, match=r"agent 'scout' at .*scout.txt is not a .md"):
        agent_harness_build_plugin_resources(
            [repo_source([{"name": "p", "agents": {"scout": "crew/scout.txt"}}])],
            str(cache_dir),
        )


@pytest.mark.unit
def test_an_explicit_map_suppresses_the_manifest_for_both_kinds_and_hooks(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill, make_agent: MakeAgent
) -> None:
    write_manifest(
        repo_path,
        {
            "name": "my-plugin",
            "hooks": {"SessionStart": [{"hooks": [{"command": "inline"}]}]},
        },
    )
    make_skill(repo_path / "skills" / "ignored-by-the-map")
    make_skill(repo_path / "elsewhere" / "picked")
    make_agent(repo_path / "agents" / "scout.md")

    result = agent_harness_build_plugin_resources(
        [
            repo_source(
                [{"name": "my-plugin", "skills": {"picked": "elsewhere/picked"}}]
            )
        ],
        str(cache_dir),
    )

    assert names(result["skills"]) == ["picked"]
    assert result["agents"] == []
    assert result["hooks"] == []


@pytest.mark.unit
def test_an_explicit_mode_plugin_is_rooted_at_its_source(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    hooks_dir = repo_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "hooks.json").write_text(json.dumps({"SessionStart": ["repo-root"]}))
    make_skill(repo_path / "skills" / "alpha")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "loose", "skills": {"alpha": "skills/alpha"}}])],
        str(cache_dir),
    )

    assert result["skills"][0]["plugin_root"] == str(repo_path)
    assert result["hooks"] == []


# =============================================================================
# Paths from upstream manifests may not escape the source checkout
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize("escape", ["/etc", "../outside"])
def test_marketplace_source_may_not_escape_the_repo(
    repo_path: Path, cache_dir: Path, escape: str
) -> None:
    write_marketplace(repo_path, {"plugins": [{"name": "my-plugin", "source": escape}]})

    with pytest.raises(ValueError, match=r"plugin my-plugin: marketplace source"):
        agent_harness_build_plugin_resources(
            [repo_source([{"name": "my-plugin"}])], str(cache_dir)
        )


@pytest.mark.unit
@pytest.mark.parametrize("escape", ["/opt", "../.."])
def test_marketplace_plugin_root_may_not_escape_the_repo(
    repo_path: Path, cache_dir: Path, escape: str
) -> None:
    write_marketplace(
        repo_path,
        {
            "metadata": {"pluginRoot": escape},
            "plugins": [{"name": "my-plugin", "source": "mine"}],
        },
    )

    with pytest.raises(ValueError, match=r"plugin my-plugin: marketplace pluginRoot"):
        agent_harness_build_plugin_resources(
            [repo_source([{"name": "my-plugin"}])], str(cache_dir)
        )


@pytest.mark.unit
@pytest.mark.parametrize("kind", ["skills", "agents"])
@pytest.mark.parametrize("escape", ["/usr/share", "../../elsewhere"])
def test_manifest_resource_paths_may_not_escape_the_plugin(
    repo_path: Path, cache_dir: Path, kind: str, escape: str
) -> None:
    write_manifest(repo_path, {"name": "my-plugin", kind: [escape]})

    with pytest.raises(ValueError, match=rf"plugin my-plugin: manifest {kind} path"):
        agent_harness_build_plugin_resources(
            [repo_source([{"name": "my-plugin"}])], str(cache_dir)
        )


@pytest.mark.unit
@pytest.mark.parametrize("escape", ["/etc/hooks.json", "../hooks.json"])
def test_manifest_hook_paths_may_not_escape_the_plugin(
    local_root: Path, cache_dir: Path, escape: str
) -> None:
    write_manifest(local_root / "mine", {"name": "mine", "hooks": escape})

    with pytest.raises(ValueError, match=r"plugin mine: hooks path"):
        agent_harness_build_plugin_resources(
            [local_source(local_root, [{"name": "mine"}])], str(cache_dir)
        )


@pytest.mark.unit
def test_a_hook_path_in_a_list_may_not_escape_the_plugin(
    local_root: Path, cache_dir: Path
) -> None:
    write_manifest(
        local_root / "mine", {"name": "mine", "hooks": ["./hooks/a.json", "../b.json"]}
    )

    with pytest.raises(ValueError, match=r"plugin mine: hooks path"):
        agent_harness_build_plugin_resources(
            [local_source(local_root, [{"name": "mine"}])], str(cache_dir)
        )


@pytest.mark.unit
@pytest.mark.parametrize("escape", ["/etc/skill", "../outside"])
def test_an_explicit_skill_path_may_not_escape_the_source(
    repo_path: Path, cache_dir: Path, escape: str
) -> None:
    with pytest.raises(ValueError, match=r"plugin p: skill 'deployed' path"):
        agent_harness_build_plugin_resources(
            [repo_source([{"name": "p", "skills": {"deployed": escape}}])],
            str(cache_dir),
        )


@pytest.mark.unit
@pytest.mark.parametrize("escape", ["/etc/scout.md", "../scout.md"])
def test_an_explicit_agent_path_may_not_escape_the_source(
    repo_path: Path, cache_dir: Path, escape: str
) -> None:
    with pytest.raises(ValueError, match=r"plugin p: agent 'scout' path"):
        agent_harness_build_plugin_resources(
            [repo_source([{"name": "p", "agents": {"scout": escape}}])],
            str(cache_dir),
        )


# =============================================================================
# Selection of manifest-derived resources
# =============================================================================


@pytest.mark.unit
def test_include_keeps_only_the_listed_skills(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_manifest(repo_path, {"name": "my-plugin"})
    for skill in ("alpha", "beta", "gamma"):
        make_skill(repo_path / "skills" / skill)

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin", "include_skills": ["gamma", "alpha"]}])],
        str(cache_dir),
    )

    assert names(result["skills"]) == ["alpha", "gamma"]


@pytest.mark.unit
def test_exclude_drops_the_listed_agents(
    repo_path: Path, cache_dir: Path, make_agent: MakeAgent
) -> None:
    write_manifest(repo_path, {"name": "my-plugin"})
    make_agent(repo_path / "agents" / "scout.md")
    make_agent(repo_path / "agents" / "sniper.md")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin", "exclude_agents": ["sniper"]}])],
        str(cache_dir),
    )

    assert names(result["agents"]) == ["scout"]


@pytest.mark.unit
def test_an_empty_include_ships_nothing(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_manifest(repo_path, {"name": "my-plugin"})
    make_skill(repo_path / "skills" / "alpha")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin", "include_skills": []}])], str(cache_dir)
    )

    assert result["skills"] == []


@pytest.mark.unit
def test_an_absent_include_ships_everything(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_manifest(repo_path, {"name": "my-plugin"})
    make_skill(repo_path / "skills" / "alpha")
    make_skill(repo_path / "skills" / "beta")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert names(result["skills"]) == ["alpha", "beta"]


@pytest.mark.unit
def test_an_exclude_that_matches_nothing_is_fatal(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_manifest(repo_path, {"name": "my-plugin"})
    make_skill(repo_path / "skills" / "alpha")

    with pytest.raises(
        ValueError,
        match=r"exclude_skills names 'stale', which the plugin does not provide",
    ):
        agent_harness_build_plugin_resources(
            [repo_source([{"name": "my-plugin", "exclude_skills": ["stale"]}])],
            str(cache_dir),
        )


@pytest.mark.unit
def test_an_include_that_matches_nothing_is_fatal(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_manifest(repo_path, {"name": "my-plugin"})
    make_skill(repo_path / "skills" / "alpha")

    with pytest.raises(
        ValueError,
        match=r"include_skills names 'ghost', which the plugin does not provide",
    ):
        agent_harness_build_plugin_resources(
            [repo_source([{"name": "my-plugin", "include_skills": ["ghost"]}])],
            str(cache_dir),
        )


# =============================================================================
# Plugin metadata carried onto resources
# =============================================================================


@pytest.mark.unit
def test_target_agents_and_exclude_data_ride_along(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_manifest(repo_path, {"name": "my-plugin"})
    make_skill(repo_path / "skills" / "alpha")

    result = agent_harness_build_plugin_resources(
        [
            repo_source(
                [
                    {
                        "name": "my-plugin",
                        "target_agents": ["claude", "amp"],
                        "exclude_data": ["*.mp4"],
                    }
                ]
            )
        ],
        str(cache_dir),
    )

    assert result["skills"][0]["target_agents"] == ["claude", "amp"]
    assert result["skills"][0]["exclude_data"] == ["*.mp4"]


@pytest.mark.unit
def test_a_plugin_without_target_agents_reaches_every_harness(
    repo_path: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_manifest(repo_path, {"name": "my-plugin"})
    make_skill(repo_path / "skills" / "alpha")

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert result["skills"][0]["target_agents"] == []


@pytest.mark.unit
def test_sources_are_walked_in_order(
    repo_path: Path, local_root: Path, cache_dir: Path, make_skill: MakeSkill
) -> None:
    write_manifest(repo_path, {"name": "remote"})
    make_skill(repo_path / "skills" / "from-repo")
    plugin_root = write_manifest(local_root / "mine", {"name": "mine"})
    make_skill(plugin_root / "skills" / "from-local")

    result = agent_harness_build_plugin_resources(
        [
            repo_source([{"name": "remote"}]),
            local_source(local_root, [{"name": "mine"}]),
        ],
        str(cache_dir),
    )

    assert names(result["skills"]) == ["from-repo", "from-local"]


@pytest.mark.unit
def test_no_sources_still_returns_every_kind(cache_dir: Path) -> None:
    assert agent_harness_build_plugin_resources([], str(cache_dir)) == {
        "skills": [],
        "agents": [],
        "hooks": [],
    }


@pytest.mark.unit
def test_a_non_dict_plugin_entry_is_fatal(repo_path: Path, cache_dir: Path) -> None:
    with pytest.raises(ValueError, match=r"plugin entry must be a mapping"):
        agent_harness_build_plugin_resources(
            [repo_source(["shorthand"])],  # pyright: ignore[reportArgumentType]
            str(cache_dir),
        )


# =============================================================================
# Hooks come out of the same resolution pass
# =============================================================================


@pytest.mark.unit
def test_hooks_file_is_collected_with_plugin_root_resolved(
    local_root: Path, cache_dir: Path
) -> None:
    plugin_root = write_manifest(local_root / "mine", {"name": "mine"})
    hooks_dir = plugin_root / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "${CLAUDE_PLUGIN_ROOT}/bin/setup.sh",
                                }
                            ]
                        }
                    ]
                }
            }
        )
    )

    result = agent_harness_build_plugin_resources(
        [local_source(local_root, [{"name": "mine"}])], str(cache_dir)
    )

    assert names(result["hooks"]) == ["mine"]
    assert str(plugin_root) in result["hooks"][0]["content"]
    assert "${CLAUDE_PLUGIN_ROOT}" not in result["hooks"][0]["content"]


@pytest.mark.unit
def test_inline_manifest_hooks_take_precedence_over_the_hooks_file(
    local_root: Path, cache_dir: Path
) -> None:
    plugin_root = write_manifest(
        local_root / "mine",
        {
            "name": "mine",
            "hooks": {
                "SessionStart": [{"hooks": [{"type": "command", "command": "inline"}]}]
            },
        },
    )
    hooks_dir = plugin_root / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "hooks.json").write_text(json.dumps({"SessionStart": "standalone"}))

    result = agent_harness_build_plugin_resources(
        [local_source(local_root, [{"name": "mine"}])], str(cache_dir)
    )

    assert "inline" in result["hooks"][0]["content"]
    assert "standalone" not in result["hooks"][0]["content"]


@pytest.mark.unit
def test_manifest_hooks_path_reference_is_read(
    local_root: Path, cache_dir: Path
) -> None:
    plugin_root = write_manifest(
        local_root / "mine", {"name": "mine", "hooks": "./config/my-hooks.json"}
    )
    (plugin_root / "config").mkdir()
    (plugin_root / "config" / "my-hooks.json").write_text(
        json.dumps({"SessionStart": [{"hooks": [{"command": "from-path"}]}]})
    )

    result = agent_harness_build_plugin_resources(
        [local_source(local_root, [{"name": "mine"}])], str(cache_dir)
    )

    assert "from-path" in result["hooks"][0]["content"]


@pytest.mark.unit
def test_a_list_of_hook_files_is_merged(local_root: Path, cache_dir: Path) -> None:
    plugin_root = write_manifest(
        local_root / "mine",
        {"name": "mine", "hooks": ["./hooks/a.json", "./hooks/b.json"]},
    )
    hooks_dir = plugin_root / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "a.json").write_text(json.dumps({"SessionStart": ["a"]}))
    (hooks_dir / "b.json").write_text(json.dumps({"WorktreeCreate": ["b"]}))

    result = agent_harness_build_plugin_resources(
        [local_source(local_root, [{"name": "mine"}])], str(cache_dir)
    )

    merged = json.loads(result["hooks"][0]["content"])
    assert set(merged) == {"SessionStart", "WorktreeCreate"}


@pytest.mark.unit
def test_a_plugin_without_hooks_contributes_no_fragment(
    local_root: Path, cache_dir: Path
) -> None:
    write_manifest(local_root / "mine", {"name": "mine"})

    result = agent_harness_build_plugin_resources(
        [local_source(local_root, [{"name": "mine"}])], str(cache_dir)
    )

    assert result["hooks"] == []


@pytest.mark.unit
def test_a_non_strict_marketplace_entry_supplies_the_hooks(
    repo_path: Path, cache_dir: Path
) -> None:
    write_marketplace(
        repo_path,
        {
            "plugins": [
                {
                    "name": "my-plugin",
                    "source": "./",
                    "strict": False,
                    "hooks": {"SessionStart": [{"hooks": [{"command": "from-entry"}]}]},
                }
            ]
        },
    )

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert "from-entry" in result["hooks"][0]["content"]


@pytest.mark.unit
def test_marketplace_entry_hooks_win_over_plugin_json(
    repo_path: Path, cache_dir: Path
) -> None:
    write_marketplace(
        repo_path,
        {
            "plugins": [
                {
                    "name": "my-plugin",
                    "source": "./",
                    "hooks": {"SessionStart": [{"hooks": [{"command": "from-entry"}]}]},
                }
            ]
        },
    )
    write_manifest(
        repo_path,
        {
            "name": "my-plugin",
            "hooks": {"SessionStart": [{"hooks": [{"command": "from-plugin-json"}]}]},
        },
    )

    result = agent_harness_build_plugin_resources(
        [repo_source([{"name": "my-plugin"}])], str(cache_dir)
    )

    assert "from-entry" in result["hooks"][0]["content"]
    assert "from-plugin-json" not in result["hooks"][0]["content"]


@pytest.mark.unit
def test_one_plugin_declared_twice_yields_a_single_fragment(
    local_root: Path, cache_dir: Path
) -> None:
    write_manifest(
        local_root / "mine",
        {"name": "mine", "hooks": {"SessionStart": [{"hooks": [{"command": "x"}]}]}},
    )

    result = agent_harness_build_plugin_resources(
        [
            local_source(
                local_root,
                [
                    {"name": "mine", "target_agents": ["pi"]},
                    {"name": "mine", "target_agents": ["claude"]},
                ],
            )
        ],
        str(cache_dir),
    )

    assert names(result["hooks"]) == ["mine"]


@pytest.mark.unit
def test_two_plugins_sharing_a_name_with_different_hooks_is_fatal(
    local_root: Path, repo_path: Path, cache_dir: Path
) -> None:
    write_manifest(
        local_root / "mine",
        {"name": "mine", "hooks": {"SessionStart": [{"hooks": [{"command": "x"}]}]}},
    )
    write_manifest(
        repo_path,
        {"name": "mine", "hooks": {"SessionStart": [{"hooks": [{"command": "y"}]}]}},
    )

    with pytest.raises(
        ValueError, match=r"plugin mine: conflicting hook fragments from .* and "
    ):
        agent_harness_build_plugin_resources(
            [
                local_source(local_root, [{"name": "mine"}]),
                repo_source([{"name": "mine"}]),
            ],
            str(cache_dir),
        )


@pytest.mark.unit
def test_hooks_false_opts_a_plugin_out(local_root: Path, cache_dir: Path) -> None:
    plugin_root = write_manifest(
        local_root / "mine",
        {"name": "mine", "hooks": {"SessionStart": [{"hooks": [{"command": "x"}]}]}},
    )
    assert plugin_root.exists()

    result = agent_harness_build_plugin_resources(
        [local_source(local_root, [{"name": "mine", "hooks": False}])], str(cache_dir)
    )

    assert result["hooks"] == []


# =============================================================================
# Tests for agent_harness_filter_resources
# =============================================================================


@pytest.mark.unit
def test_agent_harness_filter_resources_empty_target_agents() -> None:
    """Resources with empty target_agents should be included for all agents."""
    resources: list[Any] = [
        {"name": "skill-a", "source": "/path/a", "origin": "repo", "target_agents": []},
    ]
    result = agent_harness_filter_resources(resources, "claude")
    assert len(result) == 1
    assert result[0]["name"] == "skill-a"


@pytest.mark.unit
def test_agent_harness_filter_resources_matching_agent() -> None:
    """Resources with matching target_agents should be included."""
    resources: list[Any] = [
        {
            "name": "skill-a",
            "source": "/path/a",
            "origin": "repo",
            "target_agents": ["claude", "amp"],
        },
    ]
    result = agent_harness_filter_resources(resources, "claude")
    assert len(result) == 1
    assert result[0]["name"] == "skill-a"


@pytest.mark.unit
def test_agent_harness_filter_resources_non_matching_agent() -> None:
    """Resources with non-matching target_agents should be excluded."""
    resources: list[Any] = [
        {
            "name": "skill-a",
            "source": "/path/a",
            "origin": "repo",
            "target_agents": ["amp"],
        },
    ]
    result = agent_harness_filter_resources(resources, "claude")
    assert len(result) == 0


@pytest.mark.unit
def test_agent_harness_filter_resources_normalizes_lowercase_dash_names() -> None:
    resources: list[Any] = [
        {
            "name": "Mixed_Case Skill",
            "source": "/path/a",
            "origin": "repo",
            "target_agents": [],
        },
    ]

    result = agent_harness_filter_resources(resources, "pi", "lowercase_dash")

    assert result[0]["name"] == "mixed-case-skill"
    assert resources[0]["name"] == "Mixed_Case Skill"


@pytest.mark.unit
def test_agent_harness_filter_resources_rejects_duplicate_destinations() -> None:
    resources: list[Any] = [
        {"name": "same", "source": "/path/a", "origin": "repo-a", "target_agents": []},
        {
            "name": "same",
            "source": "/path/b",
            "origin": "repo-b",
            "target_agents": ["pi"],
        },
    ]

    with pytest.raises(
        ValueError,
        match=r"Multiple resources target pi:same: /path/a and /path/b",
    ):
        agent_harness_filter_resources(resources, "pi")


@pytest.mark.unit
def test_agent_harness_filter_resources_rejects_transformed_name_collisions() -> None:
    resources: list[Any] = [
        {
            "name": "Same_Name",
            "source": "/path/a",
            "origin": "repo-a",
            "target_agents": [],
        },
        {
            "name": "same-name",
            "source": "/path/b",
            "origin": "repo-b",
            "target_agents": [],
        },
    ]

    with pytest.raises(ValueError, match=r"Multiple resources target pi:same-name"):
        agent_harness_filter_resources(resources, "pi", "lowercase_dash")


@pytest.mark.unit
def test_agent_harness_filter_resources_mixed() -> None:
    """Filter correctly handles mixed resources."""
    resources: list[Any] = [
        {"name": "for-all", "source": "/a", "origin": "repo", "target_agents": []},
        {
            "name": "for-claude",
            "source": "/b",
            "origin": "repo",
            "target_agents": ["claude"],
        },
        {"name": "for-amp", "source": "/c", "origin": "repo", "target_agents": ["amp"]},
        {
            "name": "for-both",
            "source": "/d",
            "origin": "repo",
            "target_agents": ["claude", "amp"],
        },
    ]

    claude_result = agent_harness_filter_resources(resources, "claude")
    assert len(claude_result) == 3
    names = [r["name"] for r in claude_result]
    assert "for-all" in names
    assert "for-claude" in names
    assert "for-both" in names
    assert "for-amp" not in names

    amp_result = agent_harness_filter_resources(resources, "amp")
    assert len(amp_result) == 3
    names = [r["name"] for r in amp_result]
    assert "for-all" in names
    assert "for-amp" in names
    assert "for-both" in names
    assert "for-claude" not in names


# =============================================================================
# Tests for _build_model_alias_map
# =============================================================================


@pytest.fixture
def sample_models_config() -> dict[str, Any]:
    """Sample models config matching the structure in models.yml."""
    return {
        "anthropic": {
            "haiku": {
                "version": "claude-haiku-4-5-20251001",
                "agent_harness": {
                    "aliases": {
                        "claude": "haiku",
                        "opencode": "anthropic/claude-haiku-4-5",
                    }
                },
            },
            "sonnet": {
                "version": "claude-sonnet-4-5-20250929",
                "agent_harness": {
                    "aliases": {
                        "claude": "sonnet",
                        "opencode": "anthropic/claude-sonnet-4-5",
                    }
                },
            },
            "opus": {
                "version": "claude-opus-4-5-20251101",
                "agent_harness": {
                    "aliases": {
                        "claude": "opus",
                        "opencode": "anthropic/claude-opus-4-5",
                    }
                },
            },
        },
        "openai": {
            "gpt": {
                "version": "gpt-5.4",
            }
        },
    }


@pytest.mark.unit
def test_build_model_alias_map_creates_bidirectional_mappings(
    sample_models_config: dict[str, Any],
) -> None:
    alias_map = _build_model_alias_map(sample_models_config)

    assert "sonnet" in alias_map
    assert alias_map["sonnet"]["opencode"] == "anthropic/claude-sonnet-4-5"
    assert alias_map["sonnet"]["claude"] == "sonnet"


@pytest.mark.unit
def test_build_model_alias_map_includes_full_model_names(
    sample_models_config: dict[str, Any],
) -> None:
    alias_map = _build_model_alias_map(sample_models_config)

    assert "anthropic/claude-opus-4-5" in alias_map
    assert alias_map["anthropic/claude-opus-4-5"]["claude"] == "opus"


@pytest.mark.unit
def test_build_model_alias_map_skips_models_without_harness_config() -> None:
    config: dict[str, Any] = {
        "openai": {
            "gpt": {"version": "gpt-5.4"},
        }
    }
    alias_map = _build_model_alias_map(config)
    assert alias_map == {}


@pytest.mark.unit
def test_build_model_alias_map_handles_empty_config() -> None:
    assert _build_model_alias_map({}) == {}


# =============================================================================
# Tests for agent_harness_transform_skill
# =============================================================================


@pytest.fixture
def create_skill_with_model(tmp_path: Path) -> Callable[[str, str], Path]:
    """Return a function to create a skill file with a model field."""

    def _create(name: str, model: str) -> Path:
        skill_dir = tmp_path / name
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(f"""---
name: {name}
description: A test skill
model: {model}
---

# {name}

This is the body content.
""")
        return skill_file

    return _create


@pytest.mark.unit
def test_transform_skill_content_rewrites_name_only_when_it_changes(
    sample_models_config: dict[str, Any],
) -> None:
    content = "---\nname: teach\ndescription: A test skill\n---\n\n# Teach\n"

    result = agent_harness_transform_skill_content(
        content, "claude", sample_models_config, name_override="plugin:teach"
    )

    assert result["modified"] is True
    assert "name: plugin:teach" in result["content"]

    second_result = agent_harness_transform_skill_content(
        result["content"], "claude", sample_models_config, name_override="plugin:teach"
    )

    assert second_result["modified"] is False
    assert second_result["content"] == result["content"]


@pytest.mark.unit
def test_transform_skill_replaces_model_for_opencode(
    create_skill_with_model: Callable[[str, str], Path],
    sample_models_config: dict[str, Any],
) -> None:
    skill_file = create_skill_with_model("test-skill", "sonnet")

    result = agent_harness_transform_skill(
        str(skill_file), "opencode", sample_models_config
    )

    assert result["modified"] is True
    assert "model: anthropic/claude-sonnet-4-5" in result["content"]
    assert "model: sonnet" not in result["content"]


@pytest.mark.unit
def test_transform_skill_no_change_when_same_alias(
    create_skill_with_model: Callable[[str, str], Path],
    sample_models_config: dict[str, Any],
) -> None:
    skill_file = create_skill_with_model("test-skill", "sonnet")

    result = agent_harness_transform_skill(
        str(skill_file), "claude", sample_models_config
    )

    assert result["modified"] is False


@pytest.mark.unit
def test_transform_skill_no_change_when_target_not_in_aliases(
    create_skill_with_model: Callable[[str, str], Path],
    sample_models_config: dict[str, Any],
) -> None:
    skill_file = create_skill_with_model("test-skill", "sonnet")

    result = agent_harness_transform_skill(str(skill_file), "amp", sample_models_config)

    assert result["modified"] is False


@pytest.mark.unit
def test_transform_skill_no_change_when_no_model_field(
    tmp_path: Path,
    sample_models_config: dict[str, Any],
) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("""---
name: no-model-skill
description: A skill without model
---

# Content
""")

    result = agent_harness_transform_skill(
        str(skill_file), "opencode", sample_models_config
    )

    assert result["modified"] is False


@pytest.mark.unit
def test_transform_skill_no_change_when_unknown_model(
    create_skill_with_model: Callable[[str, str], Path],
    sample_models_config: dict[str, Any],
) -> None:
    skill_file = create_skill_with_model("test-skill", "unknown-model")

    result = agent_harness_transform_skill(
        str(skill_file), "opencode", sample_models_config
    )

    assert result["modified"] is False


@pytest.mark.unit
def test_transform_skill_missing_file(
    sample_models_config: dict[str, Any],
) -> None:
    result = agent_harness_transform_skill(
        "/nonexistent/path/SKILL.md", "opencode", sample_models_config
    )

    assert result["modified"] is False
    assert result["content"] == ""


@pytest.mark.unit
def test_transform_skill_preserves_body_content(
    create_skill_with_model: Callable[[str, str], Path],
    sample_models_config: dict[str, Any],
) -> None:
    skill_file = create_skill_with_model("test-skill", "opus")

    result = agent_harness_transform_skill(
        str(skill_file), "opencode", sample_models_config
    )

    assert "# test-skill" in result["content"]


@pytest.mark.unit
def test_transform_skill_replaces_plugin_root(
    tmp_path: Path,
    sample_models_config: dict[str, Any],
) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("""---
name: my-skill
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/bin/run.sh:*)
---

Run: ${CLAUDE_PLUGIN_ROOT}/bin/run.sh
""")

    result = agent_harness_transform_skill(
        str(skill_file), "claude", sample_models_config, "/cache/my-plugin"
    )

    assert result["modified"] is True
    assert "${CLAUDE_PLUGIN_ROOT}" not in result["content"]
    assert "/cache/my-plugin/bin/run.sh" in result["content"]


@pytest.mark.unit
def test_transform_skill_no_plugin_root_when_empty(
    tmp_path: Path,
    sample_models_config: dict[str, Any],
) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("""---
name: my-skill
---

Run: ${CLAUDE_PLUGIN_ROOT}/bin/run.sh
""")

    result = agent_harness_transform_skill(
        str(skill_file), "claude", sample_models_config, ""
    )

    assert result["modified"] is False
    assert "${CLAUDE_PLUGIN_ROOT}" in result["content"]


@pytest.mark.unit
def test_transform_skill_both_model_and_plugin_root(
    tmp_path: Path,
    sample_models_config: dict[str, Any],
) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("""---
name: my-skill
model: sonnet
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/bin/run.sh:*)
---

Content here.
""")

    result = agent_harness_transform_skill(
        str(skill_file), "opencode", sample_models_config, "/cache/plugin"
    )

    assert result["modified"] is True
    assert "model: anthropic/claude-sonnet-4-5" in result["content"]
    assert "/cache/plugin/bin/run.sh" in result["content"]
    assert "${CLAUDE_PLUGIN_ROOT}" not in result["content"]


class TestRepoToCacheName:
    def test_owner_name_form(self) -> None:
        assert (
            _repo_to_cache_name("anthropics/claude-plugins-official")
            == "anthropics--claude-plugins-official"
        )

    def test_https_url(self) -> None:
        assert (
            _repo_to_cache_name("https://scm.example.com/scm/proj/my-plugin.git")
            == "scm--example--com--scm--proj--my-plugin"
        )

    def test_https_url_without_git_suffix(self) -> None:
        assert (
            _repo_to_cache_name("https://github.com/owner/repo")
            == "github--com--owner--repo"
        )

    def test_ssh_url(self) -> None:
        assert (
            _repo_to_cache_name("git@gitlab.example.com:user/repo.git")
            == "gitlab--example--com--user--repo"
        )

    def test_public_filter_matches_private(self) -> None:
        url = "https://scm.example.com/scm/proj/my-plugin.git"
        assert agent_harness_repo_to_cache_name(url) == _repo_to_cache_name(url)

    def test_no_leading_or_trailing_dashes(self) -> None:
        result = _repo_to_cache_name("https://host.com/repo.git")
        assert not result.startswith("-")
        assert not result.endswith("-")
