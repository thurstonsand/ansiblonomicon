"""Render Antigravity's host-specific configuration while preserving CLI-owned state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import librarian
import tomlkit

SCHEMA_URL = "https://antigravity.google/schemas/v1/settings.json"
CODEX_FORK_NOTE = ' Spawn it with fork_turns "none": it needs only the question, not this conversation.'
PRESERVED_SETTINGS_KEYS = (
    "model",
    "modelProvider",
    "trustedWorkspaces",
    "gcp",
    "customModelsConfig",
)
AGY_COMMENT_MATCHER = (
    "edit_file|write_file|write_to_file|replace_file_content|multi_replace_file_content"
)
DECLARED_KEYBINDINGS: dict[str, list[str]] = {
    "navigation.go_to_bottom": ["alt+shift+g"],
    "navigation.go_to_top": ["alt+g"],
    "navigation.half_page_down": ["alt+j"],
    "navigation.half_page_up": ["alt+k"],
    "subagent.jump_to_waiting": ["alt+w"],
}


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    try:
        value = cast(object, json.loads(raw))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON; refusing to overwrite") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected top-level JSON object")
    return cast(dict[str, Any], value)


def _declared_settings(models: dict[str, Any]) -> dict[str, Any]:
    # Antigravity CLI normalizes settings.json at startup and strips keys equal to
    # their defaults (enableTerminalSandbox=false, colorScheme="terminal", etc.),
    # so only non-default preferences are written here.
    return {
        "$schema": SCHEMA_URL,
        "agentMode": "accept-edits",
        "toolPermission": "always-proceed",
        "artifactReviewPolicy": "always-proceed",
        "allowNonWorkspaceAccess": True,
        "altScreenMode": "always",
        "notifications": True,
        "showTips": False,
        "showFeedbackSurvey": False,
        "model": models["google"]["gemini_neon"]["display_name"],
        "statusLine": {
            "type": "command",
            "command": "~/.gemini/antigravity-cli/statusline.sh",
        },
        "title": {
            "type": "command",
            "command": "~/.local/libexec/tab-title.py --agy",
        },
    }


def _render_settings(home: Path, models: dict[str, Any]) -> str:
    target = home / ".gemini/antigravity-cli/settings.json"
    existing = _read_json_object(target)
    settings = _declared_settings(models)
    for key in PRESERVED_SETTINGS_KEYS:
        value = existing.get(key)
        if value:
            settings[key] = value
    permissions = existing.get("permissions")
    if isinstance(permissions, dict):
        non_empty: dict[str, Any] = {
            k: v
            for k, v in cast(dict[str, Any], permissions).items()
            if isinstance(v, list) and v
        }
        if non_empty:
            settings["permissions"] = non_empty
    ordered = {key: settings[key] for key in sorted(settings)}
    return json.dumps(ordered, indent=2, ensure_ascii=False) + "\n"


def _render_keybindings(home: Path) -> str:
    """Merge alt-screen navigation bindings into AGY's normalized keybindings.json.

    Antigravity CLI expands keybindings.json in place on startup (replacing
    symlinks with a 0600 sorted single-line-array JSON file), so this merges
    into any existing entries and writes the same formatting to stay drift-free.
    """
    target = home / ".gemini/antigravity-cli/keybindings.json"
    existing = _read_json_object(target)
    merged: dict[str, Any] = {**existing, **DECLARED_KEYBINDINGS}
    lines = [
        f"  {json.dumps(key, ensure_ascii=False)}: {json.dumps(merged[key], ensure_ascii=False)}"
        for key in sorted(merged)
    ]
    return "{\n" + ",\n".join(lines) + "\n}\n"


def _render_hooks(home: Path) -> str:
    target = home / ".gemini/config/hooks.json"
    hooks = _read_json_object(target)
    hooks["command-timing"] = {
        "PreToolUse": [
            {
                "matcher": "run_command",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ~/.gemini/config/hooks/command-timing.py agy",
                        "timeout": 5,
                    }
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "run_command",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ~/.gemini/config/hooks/command-timing.py agy",
                        "timeout": 5,
                    }
                ],
            }
        ],
        "PreInvocation": [
            {
                "type": "command",
                "command": "python3 ~/.gemini/config/hooks/command-timing.py agy",
                "timeout": 5,
            }
        ],
    }
    hooks["no-chat-comments"] = {
        "PreToolUse": [
            {
                "matcher": AGY_COMMENT_MATCHER,
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ~/.gemini/config/hooks/no-chat-comments.py agy",
                        "timeout": 5,
                    }
                ],
            }
        ]
    }
    return json.dumps(hooks, indent=2, ensure_ascii=False) + "\n"


def _render_librarian_agent(home: Path, hostname: str, models: dict[str, Any]) -> str:
    generated = librarian.codex_setup(home, librarian.cli(home, hostname))
    parsed = tomlkit.parse(generated[".codex/agents/librarian.toml"])
    description = str(parsed["description"]).removesuffix(CODEX_FORK_NOTE)
    instructions = str(parsed["developer_instructions"]).strip()
    model_alias = models["google"]["gemini_neon"]["agent_harness"]["aliases"]["agy"]
    return (
        "---\n"
        "name: librarian\n"
        f"description: {json.dumps(description, ensure_ascii=False)}\n"
        f"model: {model_alias}\n"
        "subagent: true\n"
        "mainAgent: false\n"
        "---\n\n"
        f"{instructions}\n"
    )


def render(
    *,
    repo: Path,
    home: Path,
    hostname: str,
    data: dict[str, Any],
    secrets: dict[str, str],
) -> dict[str, str]:
    """Return HOME-relative Antigravity files; the caller owns modes and application."""
    del repo, secrets
    models = data.get("models")
    if not isinstance(models, dict):
        raise ValueError("data.models must contain the canonical model mapping")
    typed_models = cast(dict[str, Any], models)
    outputs = {
        ".gemini/antigravity-cli/keybindings.json": _render_keybindings(home),
        ".gemini/antigravity-cli/settings.json": _render_settings(home, typed_models),
        ".gemini/config/hooks.json": _render_hooks(home),
        ".gemini/config/agents/librarian.md": _render_librarian_agent(
            home, hostname, typed_models
        ),
    }
    if (home / ".agents/local.md").is_file():
        outputs[".gemini/config/rules/local.md"] = (
            "---\ntrigger: always_on\n---\n\n@[Local](~/.agents/local.md)\n"
        )
    return outputs
