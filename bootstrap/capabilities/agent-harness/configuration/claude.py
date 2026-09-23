"""Render Claude's host-specific configuration without a chezmoi runtime."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, cast

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATES = Path(__file__).parent / "templates"
_ENV = Environment(
    loader=FileSystemLoader(_TEMPLATES),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
    autoescape=False,
    comment_start_string="{##",
    comment_end_string="##}",
)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge dictionaries recursively, retaining order and treating null as delete."""
    result: dict[str, Any] = {}
    for key in (*base, *(key for key in overlay if key not in base)):
        if key not in overlay:
            result[key] = base[key]
        elif overlay[key] is None:
            continue
        elif isinstance(base.get(key), dict) and isinstance(overlay[key], dict):
            result[key] = _deep_merge(
                cast(dict[str, Any], base[key]),
                cast(dict[str, Any], overlay[key]),
            )
        else:
            result[key] = overlay[key]
    return result


def _existing_order(
    desired: dict[str, Any], existing: dict[str, Any]
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in existing:
        if key in desired:
            value = desired[key]
            if isinstance(value, dict) and isinstance(existing[key], dict):
                value = _existing_order(
                    cast(dict[str, Any], value),
                    cast(dict[str, Any], existing[key]),
                )
            result[key] = value
    result.update((key, value) for key, value in desired.items() if key not in result)
    return result


def _models(data: dict[str, Any]) -> dict[str, Any]:
    models = data.get("models")
    if not isinstance(models, dict):
        raise ValueError("data.models must contain the canonical model mapping")
    return cast(dict[str, Any], models)


def _base_settings(
    *, hostname: str, data: dict[str, Any], secrets: dict[str, str]
) -> dict[str, Any]:
    models = _models(data)
    env = {
        "CLAUDE_CODE_NO_FLICKER": "1",
        "CLAUDE_CODE_DISABLE_TERMINAL_TITLE": "1",
    }
    if hostname == "ML-DFC6YK6VJQ":
        try:
            env["ANTHROPIC_AUTH_TOKEN"] = secrets["ANTHROPIC_AUTH_TOKEN"]
        except KeyError as error:
            raise ValueError(
                "ANTHROPIC_AUTH_TOKEN is required on the work host"
            ) from error
    return {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "cleanupPeriodDays": 99999,
        "env": env,
        "attribution": {"commit": "", "pr": ""},
        "permissions": {
            "allow": [
                "Bash(git *)",
                "mcp__parallel-search__web_search_preview",
                "mcp__parallel-search__web_fetch",
                "Skill(updating-documentation-for-changes)",
                "Skill(git-commit-helper)",
            ],
            "deny": ["Read(**/.env)", "Read(**/.env.*)"],
            "defaultMode": "auto",
        },
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "~/.local/libexec/tab-title.py --claude-hook",
                        }
                    ]
                },
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "bun ~/.claude/scripts/session-recovery/index.ts",
                        }
                    ]
                },
            ],
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {"type": "command", "command": "~/.claude/hooks/set-title.py"}
                    ]
                }
            ],
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "node ~/.claude/hooks/force-ask-patterns.mjs",
                        }
                    ],
                }
            ],
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "~/.claude/hooks/derive-title.py",
                            "async": True,
                        },
                        {
                            "type": "command",
                            "command": "bun ~/.claude/scripts/session-recovery/index.ts",
                            "async": True,
                        },
                    ]
                }
            ],
            "SessionEnd": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "bun ~/.claude/scripts/session-recovery/index.ts",
                        }
                    ]
                }
            ],
        },
        "worktree": {"baseRef": "head"},
        "statusLine": {"type": "command", "command": "~/.claude/scripts/statusline.sh"},
        "model": models["anthropic"]["opus"]["agent_harness"]["aliases"]["claude"],
        "outputStyle": "2B",
        "sandbox": {"excludedCommands": []},
        "alwaysThinkingEnabled": True,
        "autoDreamEnabled": True,
        "skipDangerousModePermissionPrompt": True,
        "skipAutoPermissionPrompt": True,
        "theme": "auto",
        "remoteControlAtStartup": True,
        "inputNeededNotifEnabled": True,
        "agentPushNotifEnabled": True,
        "voiceEnabled": True,
        "showClearContextOnPlanAccept": True,
        "extraKnownMarketplaces": {
            "claude-plugins-official": {
                "source": {
                    "source": "github",
                    "repo": "anthropics/claude-plugins-official",
                }
            }
        },
    }


def _overlay(repo: Path, hostname: str, data: dict[str, Any]) -> dict[str, Any]:
    path = (
        repo
        / "bootstrap/capabilities/agent-harness/local"
        / hostname
        / "claude-settings-overlay.json"
    )
    if not path.exists():
        return {}
    substitutions: dict[str, str] = {}
    for tier, fields in data.get("work_models", {}).items():
        if isinstance(fields, dict):
            typed_fields = cast(dict[str, Any], fields)
            substitutions.update(
                (f"work_models.{tier}.{key}", value)
                for key, value in typed_fields.items()
                if isinstance(value, str)
            )
    raw = re.sub(
        r"\$\{([^}]+)\}",
        lambda match: substitutions.get(match.group(1), match.group(0)),
        path.read_text(),
    )
    value = cast(object, json.loads(raw))
    if not isinstance(value, dict):
        raise ValueError(f"Claude settings overlay must be an object: {path}")
    return cast(dict[str, Any], value)


def _aggregate_hooks(settings: dict[str, Any], home: Path) -> None:
    hooks = cast(dict[str, list[Any]], settings.setdefault("hooks", {}))
    for path in sorted((home / ".cache/ansiblonomicon-harness/hooks").glob("*.json")):
        try:
            fragment = cast(object, json.loads(path.read_text()))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"{path}: invalid configured hook fragment") from error
        if not isinstance(fragment, dict):
            raise ValueError(f"{path}: configured hook fragment must be an object")
        typed_fragment = cast(dict[str, Any], fragment)
        fragment_hooks = typed_fragment.get("hooks", {})
        if not isinstance(fragment_hooks, dict):
            raise ValueError(f"{path}: hook fragment 'hooks' must be an object")
        for event, entries in cast(dict[str, Any], fragment_hooks).items():
            if not isinstance(entries, list):
                raise ValueError(f"{path}: hook entries for {event!r} must be a list")
            hooks[event] = [*hooks.get(event, []), *entries]


def render(
    *,
    repo: Path,
    home: Path,
    hostname: str,
    data: dict[str, Any],
    secrets: dict[str, str],
) -> dict[str, str]:
    """Return HOME-relative Claude files; the caller owns modes and application."""
    settings = _deep_merge(
        _base_settings(hostname=hostname, data=data, secrets=secrets),
        _overlay(repo, hostname, data),
    )
    _aggregate_hooks(settings, home)
    target = home / ".claude/settings.json"
    if target.exists():
        try:
            existing = json.loads(target.read_text())
        except json.JSONDecodeError as error:
            raise ValueError(
                f"{target}: invalid JSON; refusing to overwrite"
            ) from error
        if not isinstance(existing, dict):
            raise ValueError(f"{target}: expected top-level JSON object")
        existing = cast(dict[str, Any], existing)
        if isinstance(existing.get("model"), str):
            settings["model"] = existing["model"]
        settings = _existing_order(settings, existing)

    usage = (
        repo
        / "bootstrap/capabilities/agent-harness/local"
        / hostname
        / "statusline-usage.sh"
    )
    statusline = _ENV.get_template("claude-statusline.sh.j2").render(
        statusline_usage=usage.read_text().rstrip() if usage.exists() else ""
    )
    persona = _ENV.get_template("shared-persona.md.j2").render().rstrip()
    style = (
        "---\nname: 2B\ndescription: YoRHa No.2 Type B — stoic combat android with dry wit\nkeep-coding-instructions: true\n---\n\n# 2B\n\n"
        + persona
        + "\n"
    )
    outputs = {
        ".claude/settings.json": json.dumps(settings, indent=2) + "\n",
        ".claude/scripts/statusline.sh": statusline,
        ".claude/output-styles/2b.md": style,
    }
    if hostname == "ML-DFC6YK6VJQ":
        return outputs

    models = _models(data)
    try:
        token = secrets["CLI_PROXY_API_KEY"]
    except KeyError as error:
        raise ValueError(
            "CLI_PROXY_API_KEY is required for Claude title hooks"
        ) from error
    title_prompt = (
        (repo / "bootstrap/capabilities/agent-harness/session-title-prompt.txt")
        .read_text()
        .strip()
    )
    outputs[".claude/hooks/_config.py"] = (
        '"""Rendered configuration for auto-title hooks."""\n\n'
        'API_URL = "https://aig.thurstons.house/v1/messages"\n'
        f"MODEL = {json.dumps(models['anthropic']['sonnet']['version'])}\n"
        f"TOKEN = {json.dumps(token)}\nMAX_CONTEXT_BYTES = 2_000_000\n\n"
        f'TITLE_PROMPT = """\n{title_prompt}\n"""\n'
    )
    return outputs
