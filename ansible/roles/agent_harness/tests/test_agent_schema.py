"""Tests for the agent harness adapter schema."""

from pathlib import Path
from typing import cast

from harness_filters import agent_harness_load_declarations

ROLE_ROOT = Path(__file__).parent.parent
REQUIRED_ADAPTER_FIELDS = {
    "config_root",
    "skills_dir",
    "agents_dir",
    "name_transform",
}
OPTIONAL_ADAPTER_FIELDS = {
    "cleanup_orphaned_agents",
    "cleanup_orphaned_skills",
    "cleanup_preserved_skills",
}
ALLOWED_ADAPTER_FIELDS = REQUIRED_ADAPTER_FIELDS | OPTIONAL_ADAPTER_FIELDS


def test_agent_adapters_conform_to_schema() -> None:
    declarations = agent_harness_load_declarations(
        str(ROLE_ROOT.parents[2] / "bootstrap/capabilities/agent-harness"),
        "/home/test",
    )
    agents = cast(dict[str, dict[str, object]], declarations["agents"])
    assert isinstance(agents, dict)

    for agent_name, adapter in agents.items():
        assert not REQUIRED_ADAPTER_FIELDS - adapter.keys(), agent_name
        assert not adapter.keys() - ALLOWED_ADAPTER_FIELDS, agent_name
