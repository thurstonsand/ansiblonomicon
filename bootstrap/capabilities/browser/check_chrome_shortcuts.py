#!/usr/bin/env python3
"""Check that a Chrome profile saved the extension shortcuts its host declares; never edits the profile."""

import argparse
import json
from pathlib import Path
import sys
import tomllib

GUIDE = "https://github.com/thurstonsand/ansiblonomicon/blob/main/docs/chrome.md"


def console_block(shortcuts: list[dict[str, str]]) -> str:
    """The developerPrivate calls that save these shortcuts, since Chrome's shortcut editor rejects Ctrl+Tab."""
    extensions = dict.fromkeys(s["extension"] for s in shortcuts)
    checks = [
        f'await chrome.developerPrivate.getExtensionInfo("{e}");' for e in extensions
    ]
    updates = [
        "await chrome.developerPrivate.updateExtensionCommand({\n"
        f'  extensionId: "{s["extension"]}",\n'
        f'  commandName: "{s["command"]}",\n'
        # A saved key is "<platform>:<keybinding>", in the syntax the API takes back.
        f'  keybinding: "{s["key"].split(":", 1)[1]}",\n'
        '  scope: "CHROME",\n'
        "});"
        for s in shortcuts
    ]
    return "\n".join(checks) + "\n\n" + "\n".join(updates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--declarations", type=Path, required=True)
    declarations = tomllib.loads(parser.parse_args().declarations.read_text())
    preferences = Path(declarations["preferences"]).expanduser()
    profile = preferences.parent.name
    guide = f"{GUIDE}#{declarations['guide']}"
    try:
        saved = json.loads(preferences.read_text())
    except FileNotFoundError:
        print(
            f"Cannot check Chrome {profile} extension shortcuts: {preferences}",
            file=sys.stderr,
        )
        print(f"Follow the manual setup instructions: {guide}", file=sys.stderr)
        return 1
    # Chrome omits the table until a profile saves its first extension shortcut.
    commands = saved.get("extensions", {}).get("commands", {})
    mismatches = [
        f"  {s['key']}: expected {s['extension']} / {s['command']} (Chrome scope)"
        for s in declarations["shortcuts"]
        if (actual := commands.get(s["key"], {})).get("extension") != s["extension"]
        or actual.get("command_name") != s["command"]
        or actual.get("global") is not False
    ]
    if not mismatches:
        print(
            f"Chrome {profile}: all {len(declarations['shortcuts'])} saved extension shortcuts match."
        )
        return 0
    print(f"Chrome {profile} extension shortcuts need manual setup:", file=sys.stderr)
    print("\n".join(mismatches), file=sys.stderr)
    print(
        f"In the {profile} Chrome profile, run this in the DevTools console of chrome://extensions/shortcuts:\n",
        file=sys.stderr,
    )
    print(console_block(declarations["shortcuts"]), file=sys.stderr)
    print(f"\nThen follow the rest of the setup: {guide}", file=sys.stderr)
    print(
        "Chrome can lag in saving them; if this check still fails afterwards, fully exit Chrome, including web apps, and rerun.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
