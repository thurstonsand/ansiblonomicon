"""Tests for host-profile resolution of the declared sources."""

from pathlib import Path
from typing import Any

from harness_filters import agent_harness_resolve_sources
import pytest
import yaml

ANSIBLE_ROOT = Path(__file__).parents[3]

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


def test_unrestricted_profile_receives_every_source() -> None:
    repos = [s.get("repo", s.get("local")) for s in resolve("personal")]
    assert repos == ["example/shared", "example/personal-only", "/agents"]


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


def test_an_undeclared_selection_is_absent_from_the_resolved_plugin() -> None:
    source = {"local": "/agents", "plugins": [{"name": "p"}]}

    assert plugin_named(resolve_sources([source])[0], "p") == {"name": "p"}


def test_plain_selection_list_applies_to_every_profile() -> None:
    source = {"local": "/agents", "plugins": [{"name": "p", "include_skills": ["a"]}]}

    for profile in PROFILES:
        resolved = resolve_sources([source], profile)
        assert plugin_named(resolved[0], "p")["include_skills"] == ["a"]


def test_pull_is_no_longer_a_field() -> None:
    with pytest.raises(ValueError, match=r"unknown field\(s\) pull"):
        resolve_sources([{"repo": "owner/pinned", "pull": False, "plugins": []}])


def test_extra_sources_append_after_the_declared_ones() -> None:
    extra = [{"local": "/work-agents", "plugins": [{"name": "work-only"}]}]
    assert resolve("work", extra)[-1]["local"] == "/work-agents"


def test_resolver_strips_profile_metadata_from_output() -> None:
    for profile in PROFILES:
        for source in resolve(profile):
            assert "included_on" not in source
            assert "excluded_on" not in source
            for plugin in source["plugins"]:
                assert "included_on" not in plugin
                assert "excluded_on" not in plugin


def test_explicit_maps_survive_resolution() -> None:
    explicit = plugin_named(local_source("personal"), "explicit")
    assert explicit["skills"] == {"deployed": "skills/source"}


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


def test_source_without_repo_or_local_is_fatal() -> None:
    with pytest.raises(ValueError, match=r"declare exactly one of repo or local"):
        resolve_sources([{"plugins": []}])


def test_source_with_both_repo_and_local_is_fatal() -> None:
    source: dict[str, Any] = {"repo": "a/b", "local": "/agents", "plugins": []}

    with pytest.raises(ValueError, match=r"declare exactly one of repo or local"):
        resolve_sources([source])


def test_non_dict_plugin_entry_is_fatal() -> None:
    source = {"local": "/agents", "plugins": ["shorthand"]}

    with pytest.raises(ValueError, match=r"plugin entry must be a mapping"):
        resolve_sources([source])


def test_plugins_that_are_not_a_list_is_fatal() -> None:
    with pytest.raises(ValueError, match=r"plugins must be a list"):
        resolve_sources([{"local": "/agents", "plugins": {"name": "p"}}])


def test_non_bool_hooks_is_fatal() -> None:
    with pytest.raises(ValueError, match=r"hooks must be true or false, got 'false'"):
        resolve_one({"name": "p", "hooks": "false"})


@pytest.mark.parametrize(
    "field_name", ["included_on", "excluded_on", "target_agents", "exclude_data"]
)
def test_a_bare_string_where_a_list_belongs_is_fatal(field_name: str) -> None:
    with pytest.raises(
        ValueError, match=rf"{field_name} must be a list of strings, got 'pi'"
    ):
        resolve_one({"name": "p", field_name: "pi"})


def test_a_non_string_list_entry_is_fatal() -> None:
    with pytest.raises(ValueError, match=r"exclude_data entries must be strings"):
        resolve_one({"name": "p", "exclude_data": [7]})


def test_a_bare_string_selection_map_value_is_fatal() -> None:
    with pytest.raises(
        ValueError, match=r"exclude_skills\[work\] must be a list of strings"
    ):
        resolve_one({"name": "p", "exclude_skills": {"work": "grill-me"}})


def test_an_unknown_target_harness_is_fatal() -> None:
    with pytest.raises(
        ValueError, match=r"target_agents names unknown harness 'cursor'"
    ):
        resolve_one({"name": "p", "target_agents": ["cursor"]})


@pytest.mark.parametrize("field_name", ["included_on", "excluded_on"])
def test_an_unknown_profile_name_is_fatal(field_name: str) -> None:
    with pytest.raises(
        ValueError, match=rf"{field_name} names unknown profile 'persnal'"
    ):
        resolve_one({"name": "p", field_name: ["persnal"]})


def test_an_unknown_profile_name_on_a_source_is_fatal() -> None:
    with pytest.raises(ValueError, match=r"excluded_on names unknown profile 'wrk'"):
        resolve_sources([{"local": "/agents", "excluded_on": ["wrk"], "plugins": []}])


def test_an_explicit_map_that_is_not_string_to_string_is_fatal() -> None:
    with pytest.raises(ValueError, match=r"skills must map strings to paths"):
        resolve_one({"name": "p", "skills": {"deployed": ["skills/a"]}})


def test_a_selection_for_the_other_kind_alongside_an_explicit_map_is_fatal() -> None:
    with pytest.raises(
        ValueError,
        match=r"the explicit skills map puts this plugin in explicit mode",
    ):
        resolve_one(
            {"name": "p", "skills": {"a": "skills/a"}, "exclude_agents": ["scout"]}
        )


def test_a_name_that_is_not_a_string_is_fatal() -> None:
    with pytest.raises(ValueError, match=r"plugin entry is missing a name"):
        resolve_one({"name": ["p"]})


def test_include_and_exclude_on_one_kind_is_fatal() -> None:
    with pytest.raises(
        ValueError, match=r"include_skills and exclude_skills are mutually exclusive"
    ):
        resolve_one({"name": "p", "include_skills": ["a"], "exclude_skills": ["b"]})


def test_selection_alongside_explicit_map_is_fatal() -> None:
    with pytest.raises(ValueError, match=r"the explicit agents map already selects"):
        resolve_one({"name": "p", "agents": {"a": "a.md"}, "exclude_agents": ["a"]})


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


def test_explicit_map_that_is_not_a_map_is_fatal() -> None:
    with pytest.raises(ValueError, match=r"skills must be a \{name: path\} map"):
        resolve_one({"name": "p", "skills": "skills"})


def test_selection_that_is_neither_list_nor_map_is_fatal() -> None:
    with pytest.raises(
        ValueError, match=r"exclude_skills must be a list or a profile-keyed map"
    ):
        resolve_one({"name": "p", "exclude_skills": "a"})


def test_plugin_without_a_name_is_fatal() -> None:
    with pytest.raises(ValueError, match=r"plugin entry is missing a name"):
        resolve_one({"target_agents": ["pi"]})


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
    document: dict[str, Any] = yaml.safe_load(
        (ANSIBLE_ROOT / "agent-harness.config.yml").read_text()
    )
    assert isinstance(document, dict)
    return document


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


def test_real_work_profile_excludes_claude_retitle() -> None:
    config = real_config()
    local = next(
        source
        for source in agent_harness_resolve_sources(
            config["agent_harness_sources"], "work", real_profiles(), HARNESSES
        )
        if "local" in source
    )

    assert "retitle" in plugin_named(local, "claude")["exclude_skills"]


def test_real_config_scopes_work_plugin_to_work_profile() -> None:
    config = real_config()
    sources = config["agent_harness_sources"]

    def local_plugin_names(profile: str) -> set[str]:
        local = next(
            source
            for source in agent_harness_resolve_sources(
                sources, profile, real_profiles(), HARNESSES
            )
            if "local" in source
        )
        return {plugin["name"] for plugin in local["plugins"]}

    assert "work" in local_plugin_names("work")
    assert "work" not in local_plugin_names("personal")


def test_real_work_profile_is_a_strict_subset_of_personal() -> None:
    config = real_config()
    sources = config["agent_harness_sources"]

    def names(profile: str) -> set[str]:
        return {
            str(s.get("repo", s.get("local")))
            for s in agent_harness_resolve_sources(
                sources, profile, real_profiles(), HARNESSES
            )
        }

    assert names("work") <= names("personal")
