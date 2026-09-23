"""Render user instructions shared by agent harnesses."""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES = Path(__file__).parent / "templates"
WORK_HOSTNAME = "ML-DFC6YK6VJQ"

DESTINATIONS = {
    "claude": ".claude/CLAUDE.md",
    "codex": ".codex/AGENTS.md",
    "pi": ".pi/agent/AGENTS.md",
    "opencode": ".config/opencode/AGENTS.md",
}


def render(
    *,
    repo: Path,
    home: Path,
    hostname: str,
    data: dict[str, Any],
    secrets: dict[str, str],
) -> dict[str, str]:
    """Return HOME-relative instruction files without changing the filesystem."""
    del repo, secrets
    environment = Environment(
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    template = environment.get_template("shared-instructions.md.j2")
    has_local = (
        bool(data.get("has_local_instructions", False))
        or (home / ".agents/local.md").is_file()
    )
    destinations = DESTINATIONS.items()
    if hostname == WORK_HOSTNAME:
        destinations = (
            (agent, destination)
            for agent, destination in destinations
            if agent in {"claude", "pi"}
        )
    return {
        destination: template.render(
            agent=agent,
            is_work=hostname == WORK_HOSTNAME,
            has_local_instructions=has_local,
        )
        for agent, destination in destinations
    }
