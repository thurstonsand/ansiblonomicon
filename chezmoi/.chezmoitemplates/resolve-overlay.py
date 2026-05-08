#!/usr/bin/env python3
"""Resolve settings overlay and aggregate harness hooks.

1. If a local overlay exists, resolves ${...} placeholders from local.toml
   and deep-merges it onto the base settings.
2. Aggregates any hook fragments from the agent-harness cache into the
   hooks section of the final output.

Usage: resolve-overlay.py <base.json>
Output: final merged JSON to stdout.
"""

import json
from pathlib import Path
import sys
import tomllib
from typing import Any

SCRIPT_DIR = Path(__file__).parent
CHEZMOI_DATA = SCRIPT_DIR.parent / ".chezmoidata" / "local.toml"
OVERLAY = SCRIPT_DIR / "local" / "claude-settings-overlay.json"
HARNESS_HOOKS_DIR = Path.home() / ".cache" / "ansiblonomicon-harness" / "hooks"


def deepmerge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into base. Overlay wins. Null deletes."""
    result: dict[str, Any] = {}
    for key in list(base.keys()) + [k for k in overlay if k not in base]:
        if key in overlay:
            if overlay[key] is None:
                continue
            if (
                key in base
                and isinstance(base[key], dict)
                and isinstance(overlay[key], dict)
            ):
                result[key] = deepmerge(base[key], overlay[key])
            else:
                result[key] = overlay[key]
        else:
            result[key] = base[key]
    return result


def load_substitutions() -> dict[str, str]:
    if not CHEZMOI_DATA.exists():
        return {}
    data = tomllib.loads(CHEZMOI_DATA.read_text())
    models = data.get("claude_code_models", {})
    return {f"claude_code_models.{k}": v for k, v in models.items() if isinstance(v, str)}


def resolve_overlay(subs: dict[str, str]) -> str:
    raw = OVERLAY.read_text()
    for key, val in subs.items():
        raw = raw.replace("${" + key + "}", val)
    return raw


def merge_harness_hooks(settings: dict[str, Any]) -> dict[str, Any]:
    """Aggregate hook fragments from agent-harness cache into settings."""
    if not HARNESS_HOOKS_DIR.is_dir():
        return settings

    hook_files = sorted(HARNESS_HOOKS_DIR.glob("*.json"))
    if not hook_files:
        return settings

    hooks: dict[str, list[Any]] = dict(settings.get("hooks", {}))

    for hook_file in hook_files:
        try:
            fragment = json.loads(hook_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        fragment_hooks = fragment.get("hooks", {})
        for event, entries in fragment_hooks.items():
            if not isinstance(entries, list):
                continue
            if event not in hooks:
                hooks[event] = []
            hooks[event] = list(hooks[event]) + entries

    if hooks:
        settings = {**settings, "hooks": hooks}
    return settings


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <base.json>", file=sys.stderr)
        sys.exit(1)

    base_path = Path(sys.argv[1])
    if not base_path.exists():
        print(f"Base file not found: {base_path}", file=sys.stderr)
        sys.exit(1)

    base = json.loads(base_path.read_text())

    if OVERLAY.exists():
        subs = load_substitutions()
        if not subs or not all(subs.values()):
            rendered = OVERLAY.read_text()
        else:
            rendered = resolve_overlay(subs)
        overlay = json.loads(rendered)
        merged = deepmerge(base, overlay)
    else:
        merged = base

    merged = merge_harness_hooks(merged)

    json.dump(merged, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
