#!/usr/bin/env python3
"""Render editor application content to stdout for native mise files."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, cast

import jsonc  # pyright: ignore[reportMissingTypeStubs]
import yaml

BASE = Path(__file__).parent / "files" / "baselines"


def read_jsonc(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], jsonc.loads((BASE / name).read_text()))


def read_models(path: Path) -> dict[str, Any]:
    document = cast(dict[str, Any], yaml.safe_load(path.read_text()))
    return cast(dict[str, Any], document["models"])


def omarchy_vscode_theme() -> str:
    # Mirrors omarchy-theme-set-vscode so a reconcile keeps whatever theme Omarchy last applied.
    descriptor = Path.home() / ".local/state/omarchy/current/theme/vscode.json"
    if descriptor.exists():
        return str(json.loads(descriptor.read_text())["name"])
    return "Omarchy"


def vscode_settings(args: argparse.Namespace) -> dict[str, Any]:
    result = read_jsonc("vscode-settings.jsonc")
    result["editor.fontFamily"] = args.proportional_font
    result["editor.fontSize"] = args.font_size
    result["terminal.integrated.fontFamily"] = args.monospace_font
    result["terminal.integrated.fontSize"] = args.font_size
    gopls = cast(dict[str, Any], result["gopls"])
    gopls.pop("local", None)
    gopls.pop("buildFlags", None)
    result.pop("go.formatFlags", None)
    if args.go_local_imports:
        gopls["local"] = args.go_local_imports
        result["go.formatFlags"] = ["-local", args.go_local_imports]
    if args.gopls_build_flags:
        gopls["buildFlags"] = [args.gopls_build_flags]
    if args.profile == "omarchy":
        result["update.mode"] = "none"
        result["workbench.colorTheme"] = omarchy_vscode_theme()
    return result


def zed_settings(args: argparse.Namespace, catalogue: dict[str, Any]) -> dict[str, Any]:
    result = read_jsonc("zed-settings.jsonc")
    result["buffer_font_family"] = args.monospace_font
    result["buffer_font_size"] = args.font_size
    result["ui_font_family"] = args.proportional_font
    result["ui_font_size"] = args.font_size + 1
    if args.profile == "work":
        cast(dict[str, Any], result["languages"])["JSON"] = {"format_on_save": "off"}
        return result
    if args.profile == "omarchy":
        result["theme"] = "Omazed"
        del result["icon_theme"]

    sol = catalogue["openai"]["gpt_sol"]
    high = sol["variants"]["high"]
    result["language_models"] = {
        "openai": {
            "available_models": [
                {
                    "name": sol["version"],
                    "display_name": sol["display_name"],
                    "max_tokens": sol["max_input"],
                    "max_output_tokens": sol["max_output"],
                    "max_completion_tokens": sol["max_output"],
                },
                {
                    "name": high["id"],
                    "display_name": high["display_name"],
                    "reasoning_effort": "high",
                    "max_tokens": sol["max_input"],
                    "max_output_tokens": sol["max_output"],
                    "max_completion_tokens": sol["max_output"],
                },
            ],
            "api_url": "https://aig.thurstons.house/v1",
        },
        "google": {"api_url": "https://aig.thurstons.house"},
        "anthropic": {"api_url": "https://aig.thurstons.house"},
        "openai_compatible": {
            "Cerebras": {
                "api_url": "https://api.cerebras.ai/v1",
                "available_models": [
                    {
                        "name": "qwen-3-coder-480b",
                        "max_tokens": 64000,
                        "max_output_tokens": 8000,
                        "max_completion_tokens": 8000,
                        "capabilities": {
                            "tools": True,
                            "images": False,
                            "parallel_tool_calls": True,
                            "prompt_cache_key": True,
                        },
                    }
                ],
            }
        },
    }
    agent = cast(dict[str, Any], result["agent"])
    opus = catalogue["anthropic"]["opus"]["version"]
    flash = catalogue["google"]["gemini_flash"]["version"]
    agent.update(
        default_model={"provider": "anthropic", "model": opus},
        inline_assistant_model={"provider": "anthropic", "model": opus},
        commit_message_model={"provider": "google", "model": flash},
        thread_summary_model={"provider": "google", "model": flash},
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("zed", "vscode"))
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument(
        "--profile", choices=("personal", "work", "omarchy"), required=True
    )
    parser.add_argument("--monospace-font", required=True)
    parser.add_argument("--proportional-font", required=True)
    parser.add_argument("--font-size", type=int, required=True)
    parser.add_argument("--go-local-imports")
    parser.add_argument("--gopls-build-flags")
    args = parser.parse_args()
    catalogue = read_models(args.models)
    if args.kind == "zed":
        value: Any = zed_settings(args, catalogue)
    else:
        value = vscode_settings(args)
    json.dump(value, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
