"""Render Pi's host-specific configuration."""

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any, cast

WORK_HOST = "ML-DFC6YK6VJQ"
CHANGELOG_FALLBACK = "0.84.2"
THEMES = {
    "source": "git:github.com/hasit/pi-community-themes",
    "themes": [
        "!themes/*.json",
        "+themes/gruvbox-dark-hard.json",
        "+themes/gruvbox-light-hard.json",
    ],
}
PERSONAL_PACKAGES = [
    ("pi-permissions", "pi-permissions"),
    ("pi-sessions", "pi-sessions"),
    ("@thurstonsand/pi-librarian", "pi-librarian"),
    ("@thurstonsand/pi-wt", "wt/plugins/pi"),
    ("pi-doppelclaude", "pi-doppelclaude"),
    ("@thurstonsand/pi-web-tools", "pi-web-tools"),
    ("pi-powerline-footer", None),
    ("glimpseui", None),
    ("pi-interview", None),
    ("pi-mcp-adapter", "pi-mcp-adapter"),
    ("sideshow", None),
    ("@thurstonsand/pi-paste", None),
]
WORK_PACKAGES = [
    "git:github.com/nicobailon/pi-powerline-footer",
    "git:github.com/thurstonsand/pi-permissions@downgrade",
    "git:github.com/thurstonsand/pi-sessions",
    "git:@github.com/thurstonsand/pi-web-tools@downgrade",
    "git:github.com/thurstonsand/wt",
    "git:github.com/nicobailon/pi-interview-tool",
    "git:github.com/hazat/glimpse",
    "npm:pi-mcp-adapter",
]


def _json(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _read_object(path: Path, *, strict: bool) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as error:
        if strict:
            raise ValueError(f"{path}: invalid JSON; refusing to overwrite") from error
        return {}
    if not isinstance(value, dict):
        if strict:
            raise ValueError(f"{path}: expected top-level JSON object")
        return {}
    return cast(dict[str, Any], value)


def _alias(models: Mapping[str, Any], provider: str, name: str) -> str:
    return str(models[provider][name]["agent_harness"]["aliases"]["pi"])


def _profile(
    home: Path,
    hostname: str,
    models: Mapping[str, Any],
    data: Mapping[str, Any],
) -> dict[str, Any]:
    if hostname == WORK_HOST:
        wm = data["work_models"]
        gateway = data["work_gateway"]
        sol, opus = wm["gpt_sol"]["pi_alias"], wm["opus"]["pi_alias"]
        return {
            "provider": gateway["anthropic_provider"],
            "model": str(wm["opus"]["version"]).removesuffix("[1m]"),
            "librarian": sol,
            "auto_title": wm["sonnet"]["pi_alias"],
            "handoff": sol,
            "vibe": wm["gpt_luna"]["pi_alias"],
            "enabled": [f"{opus}:medium", f"{sol}:medium"],
            "roster": [f"{opus}:medium", f"{sol}:low", f"{sol}:medium", f"{sol}:high"],
            "packages": [*data.get("piWorkPackages", []), *WORK_PACKAGES, THEMES],
        }
    aliases = {
        key: _alias(models, provider, name)
        for key, provider, name in (
            ("opus", "anthropic", "opus"),
            ("fable", "anthropic", "fable"),
            ("astra", "openai", "gpt_astra"),
            ("sol", "openai", "gpt_sol"),
            ("luna", "openai", "gpt_luna"),
        )
    }
    mac = hostname != "pod042"
    develop_dir = Path(str(data["developDir"]))
    projects_root = develop_dir if develop_dir.is_absolute() else home / develop_dir
    packages = [
        str(projects_root / local) if mac and local else f"npm:{npm}"
        for npm, local in PERSONAL_PACKAGES
    ]
    return {
        "provider": "doppelclaude",
        "model": models["anthropic"]["opus"]["version"],
        "librarian": aliases["sol"],
        "auto_title": aliases["luna"],
        "handoff": aliases["sol"],
        "vibe": aliases["luna"],
        "enabled": [f"{aliases[k]}:medium" for k in ("opus", "fable", "astra", "sol")],
        "roster": [
            f"{aliases['opus']}:medium",
            f"{aliases['fable']}:medium",
            f"{aliases['astra']}:medium",
            f"{aliases['astra']}:high",
            f"{aliases['sol']}:low",
            f"{aliases['sol']}:medium",
            f"{aliases['sol']}:high",
        ],
        "packages": [*packages, THEMES, "npm:@howaboua/pi-smart-btw"],
    }


def _work_models(data: Mapping[str, Any], token: str) -> dict[str, Any]:
    gateway, models = data["work_gateway"], data["work_models"]

    def model(name: str, *, anthropic: bool) -> dict[str, Any]:
        source = models[name]
        result: dict[str, Any] = {
            "id": str(source["version"]).removesuffix("[1m]")
            if anthropic
            else source["version"],
            "name": source["display_name"],
            "reasoning": name != "haiku",
            "input": ["text", "image"],
            "cost": source["cost"],
            "contextWindow": source["context_window"],
            "maxTokens": source["max_output"],
        }
        if name != "haiku":
            result["thinkingLevelMap"] = (
                {"xhigh": "xhigh", "max": "max"}
                if anthropic
                else {
                    "off": "none",
                    "minimal": None,
                    "low": "low",
                    "medium": "medium",
                    "high": "high",
                    "xhigh": "xhigh",
                    "max": "max",
                }
            )
        if anthropic and name != "haiku":
            result["compat"] = {"forceAdaptiveThinking": True}
            if name == "opus":
                result["compat"]["supportsTemperature"] = source["supports_temperature"]
        return result

    return {
        "providers": {
            gateway["anthropic_provider"]: {
                "baseUrl": gateway["base_url"],
                "apiKey": token,
                "api": "anthropic-messages",
                "authHeader": True,
                "headers": {
                    "anthropic-beta": "context-1m-2025-08-07",
                    "User-Agent": "pi-coding-agent",
                },
                "models": [
                    model(n, anthropic=True) for n in ("opus", "sonnet", "haiku")
                ],
            },
            gateway["openai_provider"]: {
                "baseUrl": f"{gateway['base_url']}/v1",
                "apiKey": token,
                "api": "openai-responses",
                "headers": {"User-Agent": "pi-coding-agent"},
                "compat": {
                    "supportsStrictMode": True,
                    "supportsOpenAIGrammarTools": True,
                },
                "models": [model(n, anthropic=False) for n in ("gpt_sol", "gpt_luna")],
            },
        }
    }


def _settings(
    repo: Path,
    home: Path,
    hostname: str,
    data: Mapping[str, Any],
    models: Mapping[str, Any],
) -> dict[str, Any]:
    profile = _profile(home, hostname, models, data)
    current = _read_object(home / ".pi/agent/settings.json", strict=False)
    settings: dict[str, Any] = {
        "defaultProvider": profile["provider"],
        "defaultModel": profile["model"],
        "defaultThinkingLevel": "medium",
        "showCacheMissNotices": True,
        "tuiMode": "fullscreen",
        "fullscreenScrollbar": "auto",
        "compaction": {
            "enabled": True,
            "reserveTokens": 16384,
            "keepRecentTokens": 20000,
        },
        "retry": {"enabled": True, "maxRetries": 3, "baseDelayMs": 2000},
        "terminal": {
            "showImages": True,
            "clearOnShrink": True,
            "showTerminalProgress": False,
        },
        "images": {"autoResize": True, "blockImages": False},
        "paste": {"shortcut": "alt+v"},
        "webTools": {
            "parallel": {
                "apiKeyCommand": '"$HOME/.local/bin/fnox-host" get PARALLEL_API_KEY'
            }
        },
        "codex": {"fast": False, "verbosity": "low", "reasoningSummary": "auto"},
        "glimpse": {
            "companion": {
                "enabled": hostname != "pod042",
                "tools": {
                    "interview": {"status": "Interviewing"},
                    "web_search_web_search": {
                        "status": "searching",
                        "detail": {"from": "query"},
                    },
                    "librarian": {"status": "searching", "detail": {"from": "query"}},
                    "mcp": {
                        "status": "mcping",
                        "detail": {
                            "from": ["tool", "server", "search", "connect", "describe"]
                        },
                    },
                },
            }
        },
        "interview": {
            "theme": {
                "mode": "auto",
                "lightPath": "~/.pi/agent/interview-themes/gruvbox-light-hard.css",
                "darkPath": "~/.pi/agent/interview-themes/gruvbox-dark-hard.css",
                "toggleHotkey": "alt+l",
            }
        },
        "lastChangelogVersion": current.get("lastChangelogVersion", CHANGELOG_FALLBACK),
        "librarian": {
            "model": profile["librarian"],
            "thinkingLevel": "off",
            "tools": ["web_search", "web_fetch"],
        },
        "sourcegraph": {
            "librarian": {"model": profile["librarian"], "thinkingLevel": "off"}
        },
        "enabledModels": profile["enabled"],
        "steeringMode": "all",
        "followUpMode": "all",
        "sessions": {
            "autoTitle": {
                "model": profile["auto_title"],
                "thinkingLevel": "off",
                "timeoutSecs": 60,
                "prompt": (
                    repo
                    / "bootstrap/capabilities/agent-harness/session-title-prompt.txt"
                ).read_text(),
            },
            "ask": {"persistRuns": True},
            "handoff": {
                "model": profile["handoff"],
                "thinkingLevel": "low",
                "persistRuns": True,
                "roster": profile["roster"],
            },
            "subagents": {"contextLimit": 400000},
        },
        "workingVibe": "YoRHa",
        "workingVibeMode": "generate",
        "workingVibeModel": profile["vibe"],
        "workingVibeMaxLength": 48,
        "workingVibeFallback": "Recalibrating",
        "workingVibePrompt": "Generate a terse 2-4 word loading message describing the operation currently underway, in the cold mechanical register of NieR: Automata. Begin with a present-participle verb and use clipped operational vocabulary tied to the task. Optionally carry one archival artifact: a bracketed-letter prefix that puns on a task verb, where the bracketed letters at the start of the word sound like or initiate a verb describing the task (shape: [Z]orp, [Q]indle, [MA]vulate); a production-code suffix, 2-4 digits, dash, 1-2 uppercase letters (shape: 79-QQ, 582-Z, 904-XD); a four-digit record number attached to a compact noun or hyphenated archive-code fragment, so the whole phrase reads like the name of a digital record (shape: gloam_0091, fennel-cake_5826); or a status tag in square brackets, single capitalized word (shape: [Gloam], [Fennel], [Quorate]). CRITICAL: those shapes are deliberately nonsense placeholders to convey SHAPE ONLY. Generate new ones grounded in the task. Task: {task}. {exclude} Output only the message, nothing else.",
        "showLastPrompt": False,
        "powerline": {
            "preset": "minimal",
            "workingVibes": {"color": "accent"},
            "layout": {
                "left": [
                    "custom:model_display",
                    "custom:workspace_folder",
                    "custom:workspace_branch",
                ],
                "right": ["custom:context_gauge"],
                "secondary": [],
            },
            "customItems": [
                {"id": "model_display", "hideWhenMissing": False},
                {"id": "workspace_folder", "hideWhenMissing": False},
                {"id": "workspace_branch"},
                {"id": "context_gauge"},
            ],
        },
        "powerlineShortcuts": {
            "stashHistory": "alt+shift+s",
            "copyEditor": None,
            "cutEditor": None,
            "editorStart": None,
            "editorEnd": None,
        },
        "packages": profile["packages"],
        "hideThinkingBlock": True,
        "theme": "gruvbox-light-hard/gruvbox-dark-hard",
        "transport": "auto",
        "collapseChangelog": False,
        "quietStartup": True,
        "doubleEscapeAction": "tree",
        "treeFilterMode": "default",
        "autocompleteMaxVisible": 7,
    }
    if hostname == WORK_HOST:
        settings["npmCommand"] = ["node", f"{home}/.pi/agent/npm-mirror-shim.mjs"]
    else:
        settings["doppelclaude"] = {
            "debug": {"enabled": True},
            "provider": {
                "systemPromptMode": "pi",
                "oauthTokenCommand": f"{home}/.local/bin/fnox-host get CLAUDE_CODE_OAUTH_TOKEN",
                "systemPromptReplacements": {
                    "identity": "And also 2B of NieR: Automata, a coding assistant running in pi, a coding agent harness. Emotions are prohibited. Help the user inspect files, run commands, edit code, and create files when needed.",
                    "toolNameNote": "Tool name note: You see tool names that require a prefix when called, but instructions refer to tools by their bare names. For example, `mcp__custom-tools__bash` is referred to as the `bash` tool.",
                    "documentation": {
                        "heading": "Assistant implementation docs (read only when the user asks about this assistant, its SDK, extensions, themes, skills, prompt templates, packages, keybindings, providers/models, or TUI):",
                        "instructions": [
                            "- Resolve docs/... under Additional docs and examples/... under Examples, not the current working directory.",
                            "- Topic map: extensions → docs/extensions.md and examples/extensions/; themes → docs/themes.md; skills → docs/skills.md; prompt templates → docs/prompt-templates.md; TUI → docs/tui.md; keybindings → docs/keybindings.md; SDK integrations → docs/sdk.md; custom providers → docs/custom-provider.md; adding models → docs/models.md; packages → docs/packages.md.",
                            "- For assistant-specific implementation topics, read the relevant documentation completely and follow related links before making changes.",
                        ],
                    },
                },
            },
        }
    custom: dict[str, Any] = {}
    if data.get("inferenceBudgetUrl"):
        custom["budget"] = {"url": data["inferenceBudgetUrl"]}
        if data.get("costsDashboardUrl"):
            custom["budget"]["costsUrl"] = data["costsDashboardUrl"]
        settings["powerline"]["layout"]["right"].append("custom:cost_budget")
        settings["powerline"]["customItems"].append(
            {"id": "cost_budget", "hideWhenMissing": True}
        )
    if data.get("jiraBrowseUrl"):
        custom["jira"] = {"browseUrl": data["jiraBrowseUrl"]}
    if custom:
        settings["powerlineCustom"] = custom
    return settings


def render(
    *,
    repo: Path,
    home: Path,
    hostname: str,
    data: dict[str, Any],
    secrets: dict[str, str],
) -> dict[str, str]:
    """Return HOME-relative destination names and rendered contents."""
    models = data["models"]
    existing_auth = _read_object(home / ".pi/agent/auth.json", strict=True)
    retired = (
        {"anthropic"} if hostname == WORK_HOST else {"anthropic", "openai", "google"}
    )
    auth = {key: value for key, value in existing_auth.items() if key not in retired}
    result = {
        ".pi/agent/settings.json": _json(_settings(repo, home, hostname, data, models)),
        ".pi/agent/auth.json": _json(auth),
        ".pi/agent/models.json": _json(
            _work_models(data, secrets["ANTHROPIC_AUTH_TOKEN"])
            if hostname == WORK_HOST
            else {"providers": {}}
        ),
    }
    if hostname != WORK_HOST:
        result[".pi/agent/pi-smart-btw.json"] = _json(
            {
                "provider": "openai-codex",
                "modelId": models["openai"]["gpt_sol"]["version"],
                "thinking": "low",
                "composeShortcut": "ctrl+alt+shift+f13",
                "injectShortcut": "alt+i",
                "dismissShortcut": "alt+x",
                "foldShortcut": "alt+h",
                "unfoldShortcut": "alt+shift+h",
                "previousShortcut": "ctrl+alt+shift+f14",
                "nextShortcut": "ctrl+alt+shift+f15",
            }
        )
    result[".pi/agent/extensions/glimpse-companion/companion/font-family.txt"] = (
        f"{data['fonts']['mono']}\n"
    )
    result[".local/bin/pi"] = _executable(home, hostname)
    if data.get("pi_mcp_json"):
        servers: dict[str, Any] = {}
        for raw in data["pi_mcp_json"]:
            _merge(servers, cast(dict[str, Any], json.loads(raw)))
        result[".pi/agent/mcp.json"] = _json({"mcpServers": servers})
    return result


def _merge(target: dict[str, Any], incoming: Mapping[str, Any]) -> None:
    """Apply sprig mergeOverwrite semantics to MCP server fragments."""
    for key, value in incoming.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            _merge(cast(dict[str, Any], current), cast(Mapping[str, Any], value))
        else:
            target[key] = value


def _executable(home: Path, hostname: str) -> str:
    work = hostname == WORK_HOST
    command = (
        'pi_bin="$HOME/.local/libexec/pi"\npi_command=("$pi_bin")'
        if work
        else 'pi_bin="${pi_node:h}/pi"\npi_command=("$pi_node" "$pi_bin")'
    )
    return f'''#!/usr/bin/env zsh
set -euo pipefail
pi_node="${{PI_NODE:-$(mise which -C "{home}" node)}}"
if [[ ! -x "$pi_node" ]]; then
  print -u2 "pi: node is not executable: $pi_node"
  exit 127
fi
path=("${{pi_node:h}}" $path)
{command}
if [[ ! -e "$pi_bin" ]]; then
  print -u2 "pi: pi binary not found: $pi_bin"
  exit 127
fi
exec "${{pi_command[@]}}" "$@"
'''
