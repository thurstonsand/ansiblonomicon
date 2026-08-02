#!/usr/bin/env python3
"""Merge the declared Codex config onto whatever Codex has written for itself.

Codex and the ChatGPT desktop app write plugin registrations, marketplace
timestamps, and generated MCP server definitions straight into config.toml.
Only the declared keys are asserted; everything else is left as found, in the
position and with the comments Codex gave it.

Usage: merge-codex-config.py <overlay-toml>
Output: final merged TOML to stdout.
"""

from collections.abc import MutableMapping
from pathlib import Path
import sys
from typing import cast

import tomlkit
from tomlkit.items import Table

TARGET = Path.home() / ".codex" / "config.toml"

type Container = MutableMapping[str, object]


def merge(base: Container, overlay: Container) -> None:
    """Assert every overlay key on base, recursing into tables."""
    for key, value in overlay.items():
        current = base.get(key)
        if isinstance(current, Table) and isinstance(value, Table):
            merge(cast(Container, current), cast(Container, value))
        else:
            base[key] = value


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <overlay-toml>", file=sys.stderr)
        sys.exit(1)

    overlay = cast(Container, tomlkit.parse(sys.argv[1]))

    if TARGET.exists():
        merged = cast(Container, tomlkit.parse(TARGET.read_text()))
        merge(merged, overlay)
    else:
        merged = overlay

    sys.stdout.write(tomlkit.dumps(merged))


if __name__ == "__main__":
    main()
