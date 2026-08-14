"""Tests for the agent harness adapter schema."""

from pathlib import Path
from typing import Any

import yaml

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
    agents_file = ROLE_ROOT / "vars" / "agents.yml"
    document: dict[str, Any] = yaml.safe_load(agents_file.read_text())
    agents: dict[str, dict[str, Any]] = document["agent_harness_agents"]

    for agent_name, adapter in agents.items():
        assert not REQUIRED_ADAPTER_FIELDS - adapter.keys(), agent_name
        assert not adapter.keys() - ALLOWED_ADAPTER_FIELDS, agent_name
