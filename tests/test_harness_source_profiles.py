"""Tests for host-profile resolution of the declared sources."""

from pathlib import Path
import tomllib
from typing import Any

from harness_filters import (
    agent_harness_resolve_sources,
)
import pytest

REPO = Path(__file__).parents[1]
CAPABILITY = REPO / "bootstrap/capabilities/agent-harness"

PROFILES = ["personal", "work", "pod042", "amp_publish"]

HARNESSES = ["claude", "amp", "codex", "opencode", "pi"]

SOURCES = [
    {
        "repo": "example/shared",
        "plugins": [
            {
                "name": "shared-skills",
                "exclude_skills": {
                    "work": ["alpha", "gamma"],
                    "*": ["alpha", "beta"],
                },
            },
        ],
    },
    {
        "repo": "example/personal-only",
        "excluded_on": ["work"],
        "plugins": [{"name": "personal-tool"}],
    },
    {
        "local": "/agents",
        "plugins": [
            {"name": "everywhere"},
            {"name": "not-at-work", "excluded_on": ["work"]},
            {"name": "only-at-work", "included_on": ["work"]},
            {"name": "explicit", "skills": {"deployed": "skills/source"}},
        ],
    },
]


def resolve(
    profile: str, extra: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    return agent_harness_resolve_sources(SOURCES, profile, PROFILES, HARNESSES, extra)


def resolve_sources(
    sources: list[dict[str, Any]], profile: str = "personal"
) -> list[dict[str, Any]]:
    return agent_harness_resolve_sources(sources, profile, PROFILES, HARNESSES)


def plugin_named(source: dict[str, Any], name: str) -> dict[str, Any]:
    return next(plugin for plugin in source["plugins"] if plugin["name"] == name)


def local_source(profile: str) -> dict[str, Any]:
    return next(source for source in resolve(profile) if "local" in source)


def test_source_level_exclusion_removes_source_for_profile() -> None:
    repos = [s.get("repo", s.get("local")) for s in resolve("work")]
    assert "example/personal-only" not in repos
    assert repos == ["example/shared", "/agents"]


def test_plugin_level_exclusion_removes_plugin_for_profile() -> None:
    names = [p["name"] for p in local_source("work")["plugins"]]
    assert names == ["everywhere", "only-at-work", "explicit"]


def test_source_level_inclusion_limits_source_to_named_profiles() -> None:
    source = {
        "local": "/work-agents",
        "included_on": ["work"],
        "plugins": [{"name": "work-only"}],
    }

    assert resolve_sources([source]) == []
    assert resolve_sources([source], "work") == [
        {"local": "/work-agents", "plugins": [{"name": "work-only"}]}
    ]


def test_profile_key_replaces_the_fallback_rather_than_merging() -> None:
    shared = next(s for s in resolve("work") if s.get("repo") == "example/shared")
    assert plugin_named(shared, "shared-skills")["exclude_skills"] == ["alpha", "gamma"]


def test_fallback_applies_to_profiles_without_their_own_key() -> None:
    shared = next(s for s in resolve("personal") if s.get("repo") == "example/shared")
    assert plugin_named(shared, "shared-skills")["exclude_skills"] == ["alpha", "beta"]


def test_selection_map_without_fallback_selects_nothing_elsewhere() -> None:
    source = {
        "local": "/agents",
        "plugins": [{"name": "p", "exclude_skills": {"work": ["only-there"]}}],
    }

    resolved = resolve_sources([source])

    assert plugin_named(resolved[0], "p")["exclude_skills"] == []


def test_include_map_without_fallback_ships_nothing_elsewhere() -> None:
    source = {
        "local": "/agents",
        "plugins": [{"name": "p", "include_skills": {"work": ["only-there"]}}],
    }

    plugin = plugin_named(resolve_sources([source])[0], "p")

    assert plugin["include_skills"] == []


# ---------------------------------------------------------------------------
# Fatal config errors
# ---------------------------------------------------------------------------


def resolve_one(plugin: dict[str, Any], profile: str = "personal") -> dict[str, Any]:
    source: dict[str, Any] = {"local": "/agents", "plugins": [plugin]}
    return resolve_sources([source], profile)[0]["plugins"][0]


def test_unknown_source_field_is_fatal() -> None:
    source: dict[str, Any] = {"local": "/agents", "path": "nope", "plugins": []}

    with pytest.raises(ValueError, match=r"source /agents: unknown field\(s\) path"):
        resolve_sources([source])


def test_unknown_plugin_field_is_fatal() -> None:
    with pytest.raises(
        ValueError, match=r"plugin p: unknown field\(s\) prefix, unknown"
    ):
        resolve_one({"name": "p", "prefix": "", "unknown": 1})


def test_non_bool_hooks_is_fatal() -> None:
    with pytest.raises(ValueError, match=r"hooks must be true or false, got 'false'"):
        resolve_one({"name": "p", "hooks": "false"})


@pytest.mark.parametrize("field_name", ["included_on", "excluded_on", "exclude_data"])
def test_a_bare_string_where_a_list_belongs_is_fatal(field_name: str) -> None:
    with pytest.raises(
        ValueError, match=rf"{field_name} must be a list of strings, got 'pi'"
    ):
        resolve_one({"name": "p", field_name: "pi"})


def test_an_unknown_target_harness_is_fatal() -> None:
    with pytest.raises(
        ValueError, match=r"target_agents names unknown harness 'cursor'"
    ):
        resolve_one({"name": "p", "target_agents": ["cursor"]})


def test_profile_keyed_target_agents_collapse_per_profile() -> None:
    plugin: dict[str, Any] = {
        "name": "p",
        "target_agents": {"amp_publish": ["amp"], "*": ["claude", "pi"]},
    }

    assert resolve_one(dict(plugin))["target_agents"] == ["claude", "pi"]
    assert resolve_one(dict(plugin), "amp_publish")["target_agents"] == ["amp"]


def test_target_agents_for_other_profiles_only_drops_the_plugin() -> None:
    source: dict[str, Any] = {
        "local": "/agents",
        "plugins": [{"name": "p", "target_agents": {"amp_publish": ["amp"]}}],
    }

    assert resolve_sources([source])[0]["plugins"] == []


@pytest.mark.parametrize("field_name", ["included_on", "excluded_on"])
def test_an_unknown_profile_name_is_fatal(field_name: str) -> None:
    with pytest.raises(
        ValueError, match=rf"{field_name} names unknown profile 'persnal'"
    ):
        resolve_one({"name": "p", field_name: ["persnal"]})


def test_include_and_exclude_on_one_kind_is_fatal() -> None:
    with pytest.raises(
        ValueError, match=r"include_skills and exclude_skills are mutually exclusive"
    ):
        resolve_one({"name": "p", "include_skills": ["a"], "exclude_skills": ["b"]})


def test_unknown_profile_key_in_selection_map_is_fatal() -> None:
    with pytest.raises(
        ValueError, match=r"exclude_skills names unknown profile 'laptop'"
    ):
        resolve_one({"name": "p", "exclude_skills": {"laptop": ["a"]}})


def test_fallback_key_before_a_profile_key_is_fatal() -> None:
    with pytest.raises(
        ValueError, match=r"exclude_skills lists '\*' before 'work'; .* must come last"
    ):
        resolve_one({"name": "p", "exclude_skills": {"*": ["a"], "work": ["b"]}})


def test_config_errors_are_fatal_even_for_profiles_that_skip_the_plugin() -> None:
    with pytest.raises(ValueError, match=r"unknown field\(s\) prefix"):
        resolve_one(
            {"name": "p", "prefix": "", "excluded_on": ["personal"]}, "personal"
        )


# ---------------------------------------------------------------------------
# Property checks against the real config: no frozen copies of the data,
# only invariants that hold for any edit. The filesystem is never touched —
# the work profile's sources only exist on the work machine.
# ---------------------------------------------------------------------------


def real_config() -> dict[str, Any]:
    sources = tomllib.loads((CAPABILITY / "catalogue.toml").read_text())["sources"]
    for source in sources:
        if "local" in source:
            source["local"] = str(REPO / source["local"])
    profiles = tomllib.loads((CAPABILITY / "profiles.toml").read_text())["profiles"]
    return {"agent_harness_sources": sources, "agent_harness_profiles": profiles}


def real_profiles() -> list[str]:
    return list(real_config()["agent_harness_profiles"])


def test_real_config_resolves_cleanly_for_every_profile() -> None:
    config = real_config()
    profiles = config["agent_harness_profiles"]
    assert profiles
    for profile, declaration in profiles.items():
        assert declaration["target_agents"], profile
        resolved = agent_harness_resolve_sources(
            config["agent_harness_sources"], profile, list(profiles), HARNESSES
        )
        assert resolved, profile
        for source in resolved:
            assert "included_on" not in source
            assert "excluded_on" not in source
            for plugin in source["plugins"]:
                assert plugin["name"]


def test_real_config_scopes_work_plugin_to_work_profile() -> None:
    config = real_config()
    sources = config["agent_harness_sources"]

    def local_plugin_names(profile: str) -> set[str]:
        return {
            plugin["name"]
            for source in agent_harness_resolve_sources(
                sources, profile, real_profiles(), HARNESSES
            )
            if "local" in source
            for plugin in source["plugins"]
        }

    assert "work" in local_plugin_names("work")
    assert "work" not in local_plugin_names("personal")


def test_real_work_profile_only_adds_its_machine_local_source() -> None:
    config = real_config()
    sources = config["agent_harness_sources"]

    def names(profile: str) -> set[str]:
        return {
            str(s.get("repo", s.get("local")))
            for s in agent_harness_resolve_sources(
                sources, profile, real_profiles(), HARNESSES
            )
        }

    work_only = str(REPO / "agents/work")
    assert names("work") - {work_only} <= names("personal")
