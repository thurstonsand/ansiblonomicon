"""Render Codex configuration while preserving Codex-owned TOML state."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, cast

import tomlkit
from tomlkit.items import Table

WORK_HOST = "ML-DFC6YK6VJQ"
TRUSTED_PROJECTS = (
    "nixonomicon",
    "anypod",
    "ansiblonomicon",
    "pi-sessions",
    "ghosttykit",
    "flux-keyboard-sdk",
)
type Container = MutableMapping[str, object]


def _merge(base: Container, overlay: Container) -> None:
    for key, value in overlay.items():
        current = base.get(key)
        if isinstance(current, Table) and isinstance(value, Table):
            _merge(cast(Container, current), cast(Container, value))
        else:
            base[key] = value


def _declared(
    *, model: str, projects_root: Path, is_work: bool, tui_theme: str
) -> dict[str, Any]:
    declared: dict[str, Any] = {
        "model_reasoning_effort": "medium",
        "model_reasoning_summary": "auto",
    }
    if not is_work:
        declared |= {
            "model": model,
            # The app labels exactly this triple as its "Full access" permission mode.
            "approval_policy": "never",
            "approvals_reviewer": "user",
            "sandbox_mode": "danger-full-access",
            "web_search": "live",
        }
    declared["features"] = {
        "prevent_idle_sleep": True,
        "memories": True,
        "default_mode_request_user_input": True,
        "chronicle": not is_work,
        "artifact": not is_work,
    }
    declared["tui"] = {
        "theme": tui_theme,
        "status_line": [
            "context-remaining",
            "model-with-reasoning",
            "project-root",
            "git-branch",
        ],
    }
    if not is_work:
        declared["projects"] = {
            **{
                str(projects_root / name): {"trust_level": "trusted"}
                for name in TRUSTED_PROJECTS
            },
            "/": {"trust_level": "trusted"},
        }
    declared["desktop"] = {
        "followUpQueueMode": "steer",
        "mac-menu-bar-enabled": False,
        "preventSleepWhileRunning": True,
        "hotkey-window-projectless-default-enabled": True,
        "appearanceLightCodeThemeId": "vercel",
        "appearanceDarkCodeThemeId": "vercel",
        "usePointerCursors": True,
        "selected-avatar-id": "custom:2b",
        "open-local-url-in-target-preference": "in-app-browser",
        "git-always-force-push": True,
        "dock-icon-preference": "app-default",
        "open-in-target-preferences": {"global": "zed"},
    }
    return declared


def render(
    *,
    repo: Path,
    home: Path,
    hostname: str,
    data: dict[str, Any],
    secrets: dict[str, str],
) -> dict[str, str]:
    """Return HOME-relative Codex files; malformed live TOML is refused."""
    del secrets
    models = data.get("models")
    if not isinstance(models, dict):
        raise ValueError("data.models must contain the canonical model mapping")
    models = cast(dict[str, Any], models)
    # On Omarchy, the theme-set hook owns the TUI theme file and the desktop chrome tables.
    chrome_path = None
    if hostname == "type-a-no2":
        tui_theme = "omarchy"
    else:
        background_path = home / ".terminal-bg"
        background = (
            background_path.read_text().strip() if background_path.exists() else "dark"
        )
        tui_theme = f"solitude-{background}"
        chrome_path = (
            repo / "bootstrap/capabilities/terminal-theme/solitude/codex-chrome.toml"
        )
    develop_dir = Path(str(data["developDir"]))
    projects_root = develop_dir if develop_dir.is_absolute() else home / develop_dir
    overlay = cast(Container, tomlkit.document())
    overlay.update(
        _declared(
            model=models["openai"]["gpt_astra"]["version"],
            projects_root=projects_root,
            is_work=hostname == WORK_HOST,
            tui_theme=tui_theme,
        )
    )
    if chrome_path is not None:
        _merge(overlay, cast(Container, tomlkit.parse(chrome_path.read_text())))
    target = home / ".codex/config.toml"
    if target.exists():
        merged = cast(Container, tomlkit.parse(target.read_text()))
        live_model = merged.get("model")
        _merge(merged, overlay)
        if isinstance(live_model, str):
            merged["model"] = live_model
    else:
        merged = overlay
    # A Codex role cannot switch provider, so its oracle runs on an OpenAI model.
    oracle = tomlkit.parse(
        (repo / "agents/project-management/agents/oracle.toml").read_text()
    )
    oracle["model"] = (
        data["work_models"]["gpt_sol"]["version"]
        if hostname == WORK_HOST
        else models["openai"]["gpt_astra"]["version"]
    )
    return {
        ".codex/config.toml": tomlkit.dumps(merged),
        ".codex/agents/oracle.toml": tomlkit.dumps(oracle),
    }
