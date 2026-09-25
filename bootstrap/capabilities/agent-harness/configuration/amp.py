"""Render Amp configuration."""

import json
from pathlib import Path
from typing import Any, cast

TEMPLATES = Path(__file__).parent / "templates"


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
    """Return HOME-relative Amp files without retrieving credentials."""
    del repo, home, hostname, data, secrets
    return {".config/amp/settings.json": _strict_json(TEMPLATES / "amp-settings.json")}
