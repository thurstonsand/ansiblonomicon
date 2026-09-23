"""Render Codex configuration while preserving Codex-owned TOML state."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, cast

from jinja2 import Environment, FileSystemLoader, StrictUndefined
import tomlkit
from tomlkit.items import Table

_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
    autoescape=False,
    comment_start_string="{##",
    comment_end_string="##}",
)
type Container = MutableMapping[str, object]


def _merge(base: Container, overlay: Container) -> None:
    for key, value in overlay.items():
        current = base.get(key)
        if isinstance(current, Table) and isinstance(value, Table):
            _merge(cast(Container, current), cast(Container, value))
        else:
            base[key] = value


def render(
    *,
    repo: Path,
    home: Path,
    hostname: str,
    data: dict[str, Any],
    secrets: dict[str, str],
) -> dict[str, str]:
    """Return HOME-relative Codex files; malformed live TOML is refused."""
    del repo, secrets
    if hostname == "ML-DFC6YK6VJQ":
        return {}
    models = data.get("models")
    if not isinstance(models, dict):
        raise ValueError("data.models must contain the canonical model mapping")
    background_path = home / ".terminal-bg"
    background = (
        background_path.read_text().strip() if background_path.exists() else "dark"
    )
    develop_dir = Path(str(data["developDir"]))
    projects_root = develop_dir if develop_dir.is_absolute() else home / develop_dir
    declared = _ENV.get_template("codex-config.toml.j2").render(
        model=models["openai"]["gpt_astra"]["version"],
        home=str(home),
        projects_root=str(projects_root),
        hostname=hostname,
        terminal_background=background,
    )
    overlay = cast(Container, tomlkit.parse(declared))
    target = home / ".codex/config.toml"
    if target.exists():
        merged = cast(Container, tomlkit.parse(target.read_text()))
        live_model = merged.get("model")
        _merge(merged, overlay)
        if isinstance(live_model, str):
            merged["model"] = live_model
    else:
        merged = overlay
    return {".codex/config.toml": tomlkit.dumps(merged)}
