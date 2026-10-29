"""Render agent-switchboard's shortlist while preserving its other live settings."""

from pathlib import Path
from typing import Any

import tomlkit

WORK_HOST = "ML-DFC6YK6VJQ"
WORKHORSE = (
    "Default workhorse, implementer; also great for prose and thinking through problems"
)
REVIEWER = (
    "Reviewer, bug-finder; cross-lab adversarial review; root-causing stubborn bugs"
)
EXPLORER = "Exploration subagent; digging for answers/explanations"
ORACLE = "Read-only expert advisor for one specific, unresolved, high-impact question; its answer is advice to verify"


def _scores(intelligence: int, taste: int, cost: int) -> str:
    return f"intelligence {intelligence}/10, taste {taste}/10, cost {cost}/10"


def _profile(hostname: str, data: dict[str, Any]) -> dict[str, str]:
    if hostname == WORK_HOST:
        wm = data["work_models"]
        return {
            # The local Claude overlay points the bare alias at the gateway's Opus.
            "claude_opus": "opus",
            "codex_reviewer": wm["gpt_sol"]["version"],
            "codex_explorer": wm["gpt_sol"]["version"],
            "pi_opus": wm["opus"]["pi_alias"],
            "pi_reviewer": wm["gpt_sol"]["pi_alias"],
            "workhorse": _scores(9, 7, 6),
            "reviewer": _scores(7, 5, 6),
            "explorer": _scores(6, 5, 7),
        }
    anthropic, openai = data["models"]["anthropic"], data["models"]["openai"]
    return {
        "claude_opus": anthropic["opus"]["agent_harness"]["aliases"]["claude"],
        "codex_reviewer": openai["gpt_astra"]["version"],
        "codex_explorer": openai["gpt_sol"]["version"],
        "pi_opus": anthropic["opus"]["agent_harness"]["aliases"]["pi"],
        "pi_reviewer": openai["gpt_astra"]["agent_harness"]["aliases"]["pi"],
        "workhorse": _scores(9, 7, 8),
        "reviewer": _scores(7, 6, 2),
        "explorer": _scores(6, 5, 7),
    }


def _pi(alias: str, effort: str) -> dict[str, Any]:
    provider, model = alias.split("/", 1)
    return {
        "harness": "pi",
        "provider": provider,
        "model": model,
        "effort": effort,
        "use": "Use when pi is requested.",
    }


def _presets(profile: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "harness": "claude",
            "model": profile["claude_opus"],
            "effort": "high",
            "use": f"{WORKHORSE} ({profile['workhorse']})",
            "default": True,
        },
        {
            "harness": "codex",
            "model": profile["codex_reviewer"],
            "effort": "high",
            "use": f"{REVIEWER} ({profile['reviewer']})",
        },
        {
            "harness": "codex",
            "model": profile["codex_explorer"],
            "effort": "low",
            "use": f"{EXPLORER} ({profile['explorer']})",
        },
        {"harness": "claude", "agent": "oracle", "use": ORACLE},
        _pi(profile["pi_opus"], "high"),
        _pi(profile["pi_reviewer"], "high"),
    ]


def render(
    *,
    repo: Path,
    home: Path,
    hostname: str,
    data: dict[str, Any],
    secrets: dict[str, str],
) -> dict[str, str]:
    """Return swb's config with the shortlist replaced; malformed live TOML is refused."""
    del repo, secrets
    relative = ".config/agent-switchboard/config.toml"
    target = home / relative
    document = (
        tomlkit.parse(target.read_text()) if target.exists() else tomlkit.document()
    )
    # Appended rather than replaced in place, which would glue the next table to the last preset.
    if "presets" in document:
        del document["presets"]
    document["presets"] = _presets(_profile(hostname, data))
    return {relative: tomlkit.dumps(document)}
