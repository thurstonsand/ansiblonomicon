"""Render OpenCode configuration."""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES = Path(__file__).parent / "templates"


def render(
    *,
    repo: Path,
    home: Path,
    hostname: str,
    data: dict[str, Any],
    secrets: dict[str, str],
) -> dict[str, str]:
    """Return HOME-relative OpenCode files."""
    del repo, home, hostname
    models = data.get("models")
    if not isinstance(models, dict):
        raise ValueError("data.models must contain the canonical model mapping")
    environment = Environment(
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    return {
        ".config/opencode/opencode.jsonc": environment.get_template(
            "opencode.jsonc.j2"
        ).render(models=models, secrets=secrets)
    }
