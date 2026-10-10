#!/usr/bin/env python3
"""Render Amp's Tune Modes pins from the `amp` block of models.yml.

Amp has no supported CI settings writer, so `settings` prints the pins for an
agent to apply through `manage_amp`, and `check` reports drift from the live
account, which must also keep the factory mode dial.
"""

import argparse
import json
import os
from pathlib import Path
import sys
from typing import TypedDict, cast
import urllib.request

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalogue import mapping

CAPABILITY = Path(__file__).resolve().parent
ROLES = ("main", "oracle", "subagents")
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
BUILTIN_MODES = ("low", "medium", "high", "ultra")
USER_INFO_URL = "https://ampcode.com/api/internal?getUserInfo"


class Pin(TypedDict):
    model: str
    effort: str


def text(entry: dict[str, object], field: str) -> str:
    value = entry[field]
    if not isinstance(value, str) or not value:
        raise ValueError(f"Expected {field} to be a non-empty string")
    return value


def builtin(value: str) -> str:
    if value not in BUILTIN_MODES:
        raise ValueError(f"Unknown built-in mode {value!r}")
    return value


def pins(roles: dict[str, object], models: dict[str, object]) -> dict[str, Pin]:
    resolved: dict[str, Pin] = {}
    for role, value in roles.items():
        if role not in ROLES:
            raise ValueError(f"Unknown role {role!r}")
        pin = mapping(value)
        provider, _, key = text(pin, "model").partition(".")
        model = mapping(mapping(models[provider])[key])
        effort = text(pin, "effort")
        if effort not in EFFORTS:
            raise ValueError(f"Unknown effort {effort!r} for {role}")
        amp_model = mapping(mapping(model["agent_harness"])["aliases"])["amp"]
        resolved[role] = {"model": cast(str, amp_model), "effort": effort}
    return resolved


def load() -> dict[str, dict[str, Pin]]:
    document = mapping(yaml.safe_load((CAPABILITY / "models.yml").read_text()))
    models, amp = mapping(document["models"]), mapping(document["amp"])
    return {
        builtin(mode): pins(mapping(roles), models)
        for mode, roles in mapping(amp["tune_modes"]).items()
    }


def live_settings() -> dict[str, object]:
    request = urllib.request.Request(
        USER_INFO_URL,
        data=json.dumps({"method": "getUserInfo", "params": {}}).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['AMP_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = mapping(mapping(json.load(response))["result"])
    return {
        "dial_modes": result["dialModes"],
        "mode_model_overrides": result["modeModelOverrides"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("settings", help="Print the mode_model_overrides value")
    commands.add_parser("check", help="Compare the live settings, using AMP_API_KEY")
    args = parser.parse_args()

    tune_modes = load()
    match args.command:
        case "settings":
            print(
                json.dumps({"mode_model_overrides": json.dumps(tune_modes)}, indent=2)
            )
        case _:
            expected: dict[str, object] = {
                "dial_modes": None,
                "mode_model_overrides": tune_modes,
            }
            live = live_settings()
            drifted = [key for key in expected if live[key] != expected[key]]
            if drifted:
                for key in drifted:
                    print(f"{key} drifted from models.yml:", file=sys.stderr)
                    print(f"  live:     {json.dumps(live[key])}", file=sys.stderr)
                    print(f"  expected: {json.dumps(expected[key])}", file=sys.stderr)
                print(
                    "Apply `mise run amp:modes` through manage_amp, and reset dial_modes to null.",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            print("Amp's factory dial and Tune Modes pins match models.yml.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, KeyError, ValueError) as error:
        print(f"amp-modes: {error!r}", file=sys.stderr)
        raise SystemExit(1) from error
