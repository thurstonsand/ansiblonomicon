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


def vscode_settings(args: argparse.Namespace) -> dict[str, Any]:
    result = read_jsonc("vscode-settings.jsonc")
    if args.editor == "Cursor":
        for key in list(result):
            if key.startswith("basedpyright.analysis."):
                result.pop(key)
        result.update(read_jsonc("cursor-settings-overlay.json"))
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
    result["ssh_connections"] = [
        {
            "host": "truenas",
            "projects": [
                {"paths": ["/mnt/performance/home/admin/Develop/nixonomicon/./"]}
            ],
        }
    ]
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


def llm_models(catalogue: dict[str, Any]) -> list[dict[str, Any]]:
    selected: list[tuple[str, str]] = []
    for provider in ("anthropic", "openai", "google"):
        provider_models = cast(dict[str, dict[str, Any]], catalogue[provider])
        for model_key in sorted(provider_models):
            model = provider_models[model_key]
            vscode = cast(dict[str, Any], model.get("vscode") or {})
            if vscode.get("include") is True:
                selected.append((str(model["display_name"]), str(model["version"])))
            if provider == "openai":
                variants = cast(dict[str, dict[str, Any]], model.get("variants") or {})
                for variant_key in sorted(variants):
                    variant = variants[variant_key]
                    if variant.get("vscode") is True:
                        selected.append(
                            (str(variant["display_name"]), str(variant["id"]))
                        )
    return [
        {
            "model_id": display,
            "model_name": version,
            "api_base": "https://aig.thurstons.house/v1",
            "api_key_name": "llm-api-key",
            "headers": None,
        }
        for display, version in selected
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("zed", "vscode", "llm"))
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--profile", choices=("personal", "work"))
    parser.add_argument("--editor", choices=("Cursor", "Windsurf", "Antigravity"))
    parser.add_argument("--monospace-font")
    parser.add_argument("--proportional-font")
    parser.add_argument("--font-size", type=int)
    parser.add_argument("--go-local-imports")
    parser.add_argument("--gopls-build-flags")
    args = parser.parse_args()
    catalogue = read_models(args.models)
    settings_required = {
        "profile": args.profile,
        "monospace-font": args.monospace_font,
        "proportional-font": args.proportional_font,
        "font-size": args.font_size,
    }
    if args.kind in {"zed", "vscode"}:
        missing = [name for name, value in settings_required.items() if value is None]
        if missing:
            parser.error(
                f"{args.kind} requires " + ", ".join(f"--{name}" for name in missing)
            )
    if args.kind == "zed":
        value: Any = zed_settings(args, catalogue)
    elif args.kind == "vscode":
        if args.editor is None:
            parser.error("vscode requires --editor")
        value = vscode_settings(args)
    else:
        value = llm_models(catalogue)
    json.dump(value, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
