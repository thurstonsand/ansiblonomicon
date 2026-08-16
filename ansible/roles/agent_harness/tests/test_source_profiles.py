"""Tests for host-profile resolution of the shared source catalogue."""

from pathlib import Path
from typing import Any

from harness_filters import agent_harness_resolve_sources
import pytest
import yaml

ANSIBLE_ROOT = Path(__file__).parents[3]

CATALOGUE = [
    {
        "repo": "example/shared",
        "pull": True,
        "plugins": [
            {
                "name": "shared-skills",
                "exclude_skills": ["alpha", "beta"],
                "exclude_skills_by_profile": {
                    "work": ["alpha", "gamma"],
                },
            },
        ],
    },
    {
        "repo": "example/personal-only",
        "pull": True,
        "excluded_on": ["work"],
        "plugins": [{"name": "personal-tool"}],
    },
    {
        "local": "/agents",
        "plugins": [
            {"name": "everywhere"},
            {"name": "not-at-work", "excluded_on": ["work"]},
            "shorthand-plugin",
        ],
    },
]


def resolve(profile: str, extra: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    return agent_harness_resolve_sources(CATALOGUE, profile, extra)


def test_source_level_exclusion_removes_source_for_profile() -> None:
    repos = [s.get("repo", s.get("local")) for s in resolve("work")]
    assert "example/personal-only" not in repos
    assert repos == ["example/shared", "/agents"]


def test_unrestricted_profile_receives_full_catalogue() -> None:
    repos = [s.get("repo", s.get("local")) for s in resolve("personal")]
    assert repos == ["example/shared", "example/personal-only", "/agents"]


def test_plugin_level_exclusion_removes_plugin_for_profile() -> None:
    local = next(s for s in resolve("work") if "local" in s)
    names = [p if isinstance(p, str) else p["name"] for p in local["plugins"]]
    assert names == ["everywhere", "shorthand-plugin"]


def test_profile_exclusion_list_replaces_base_exclusions() -> None:
    shared = next(s for s in resolve("work") if s.get("repo") == "example/shared")
    assert shared["plugins"][0]["exclude_skills"] == ["alpha", "gamma"]


def test_base_exclusions_apply_when_profile_has_no_override() -> None:
    shared = next(s for s in resolve("personal") if s.get("repo") == "example/shared")
    assert shared["plugins"][0]["exclude_skills"] == ["alpha", "beta"]


def test_extra_sources_append_after_catalogue() -> None:
    extra = [{"local": "/work-agents", "plugins": [{"name": "work-only"}]}]
    resolved = resolve("work", extra)
    assert resolved[-1]["local"] == "/work-agents"


def test_resolver_strips_profile_metadata_from_output() -> None:
    for profile in ("personal", "work"):
        for source in resolve(profile):
            assert "excluded_on" not in source
            for plugin in source["plugins"]:
                if isinstance(plugin, dict):
                    assert "excluded_on" not in plugin
                    assert "exclude_skills_by_profile" not in plugin


def test_catalogue_is_a_pass_through_for_unknown_profile_markers() -> None:
    assert resolve("pod042") == resolve("personal")


# ---------------------------------------------------------------------------
# Property checks against the real catalogue: no frozen copies of the data,
# only invariants that hold for any catalogue edit.
# ---------------------------------------------------------------------------


def real_config() -> dict[str, Any]:
    document = yaml.safe_load((ANSIBLE_ROOT / "agent-harness.config.yml").read_text())
    assert isinstance(document, dict)
    return document


def test_real_catalogue_resolves_cleanly_for_every_profile() -> None:
    config = real_config()
    profiles = config["agent_harness_profiles"]
    assert profiles
    for profile, declaration in profiles.items():
        assert declaration["target_agents"], profile
        resolved = agent_harness_resolve_sources(
            config["agent_harness_source_catalogue"], profile
        )
        assert resolved, profile
        for source in resolved:
            assert "excluded_on" not in source
            for plugin in source["plugins"]:
                if isinstance(plugin, dict):
                    assert "exclude_skills_by_profile" not in plugin


def test_real_work_profile_is_a_strict_subset_of_personal() -> None:
    config = real_config()
    catalogue = config["agent_harness_source_catalogue"]

    def names(profile: str) -> set[str]:
        return {
            str(s.get("repo", s.get("local")))
            for s in agent_harness_resolve_sources(catalogue, profile)
        }

    assert names("work") <= names("personal")
