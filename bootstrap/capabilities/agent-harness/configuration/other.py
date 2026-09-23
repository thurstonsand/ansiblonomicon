"""Render Amp, OpenCode, and small static agent configuration files."""

import json
from pathlib import Path
from typing import Any, cast

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES = Path(__file__).parent / "templates"
WORK_HOSTNAME = "ML-DFC6YK6VJQ"


def _strict_json(source: Path) -> str:
    value = cast(object, json.loads(source.read_text()))
    return json.dumps(value, indent=2) + "\n"


def render(
    *,
    repo: Path,
    home: Path,
    hostname: str,
    data: dict[str, Any],
    secrets: dict[str, str],
) -> dict[str, str]:
    """Return HOME-relative configuration files without retrieving credentials."""
    del home
    if hostname == WORK_HOSTNAME:
        return {}

    environment = Environment(
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    models = data.get("models")
    if not isinstance(models, dict):
        raise ValueError("data.models must contain the canonical model mapping")

    outputs = {
        ".config/amp/settings.json": _strict_json(TEMPLATES / "other-amp-settings.json")
    }
    outputs[".config/opencode/opencode.jsonc"] = environment.get_template(
        "other-opencode.jsonc.j2"
    ).render(models=models, secrets=secrets)
    del repo
    return outputs
