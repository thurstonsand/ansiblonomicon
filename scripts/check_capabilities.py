#!/usr/bin/env python3
"""Fail when capabilities in one bootstrap target would silently override each other.

mise merges the selected `mise.<capability>.toml` environments and gives a colliding resource to the
last one. Identical declarations are harmless, and an overlay named `<capability>-<suffix>` overrides
its base on purpose; any other collision is an accident. Hooks of the same name all run, so they never
collide, but any subset of capabilities can be selected, so they must not branch on MISE_ENV.
"""

from pathlib import Path
import re
import sys
import tomllib
from typing import Any

TARGETS = Path(__file__).resolve().parents[1] / "bootstrap/targets"
BOOTSTRAP_TABLES = (
    "packages",
    "groups",
    "users",
    "directories",
    "files",
    "services",
    "repos",
    "compose",
    "secrets",
)
MISE_ENV_READ = re.compile(r"\$\{?MISE_ENV\b")


def resources(config: dict[str, Any]) -> dict[tuple[str, ...], object]:
    found: dict[tuple[str, ...], object] = {}
    bootstrap: dict[str, Any] = config.get("bootstrap", {})
    for table in BOOTSTRAP_TABLES:
        entries: dict[str, object] = bootstrap.get(table, {})
        for name, value in entries.items():
            found[("bootstrap", table, name)] = value

    def leaves(table: dict[str, Any], path: tuple[str, ...]) -> None:
        for name, value in table.items():
            if isinstance(value, dict) and len(path) < 4:
                leaves(value, (*path, name))  # pyright: ignore[reportUnknownArgumentType]
            else:
                found[(*path, name)] = value

    for platform in ("macos", "linux"):
        leaves(bootstrap.get(platform, {}), ("bootstrap", platform))
    for table in ("dotfiles", "tasks", "env", "vars"):
        declared: dict[str, object] = config.get(table, {})
        for name, value in declared.items():
            found[(table, name)] = value
    return found


def is_overlay(base: str, overlay: str) -> bool:
    return overlay.startswith(f"{base}-")


def main() -> int:
    errors: list[str] = []
    for target in sorted(path for path in TARGETS.iterdir() if path.is_dir()):
        owners: dict[tuple[str, ...], tuple[str, object]] = {}
        for path in sorted(
            target.glob("mise.*.toml"), key=lambda path: path.name.split(".")[1]
        ):
            if ".local." in path.name:
                continue
            capability = path.name.removeprefix("mise.").removesuffix(".toml")
            config: dict[str, Any] = tomllib.loads(path.read_text())
            for key, value in resources(config).items():
                if key in owners:
                    owner, owned = owners[key]
                    if owned != value and not (
                        is_overlay(owner, capability) or is_overlay(capability, owner)
                    ):
                        errors.append(
                            f"{target.name}: {'.'.join(key)} is declared differently by "
                            f"{owner} and {capability}; give it one owner, move it to the target's "
                            f"mise.toml if several capabilities need it, or name the override "
                            f"{owner}-<suffix> to make it an overlay"
                        )
                else:
                    owners[key] = (capability, value)
            hooks: dict[str, object] = config.get("bootstrap", {}).get("hooks", {})
            for stage, hook in hooks.items():
                if MISE_ENV_READ.search(str(hook)):
                    errors.append(
                        f"{target.name}: {capability}'s {stage} hook reads MISE_ENV, but any "
                        f"subset of capabilities can be selected"
                    )
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
