"""Install declared marketplace plugins through each harness's own plugin manager."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any, cast

HARNESSES = ("claude", "codex")
MARKETPLACE_KINDS = ("github", "git")
OWNERSHIP = ".cache/ansiblonomicon-harness/configuration/plugins-owned.json"


def conform(data: dict[str, Any]) -> None:
    """Validate data.marketplaces and data.plugins in place."""
    marketplaces = data.setdefault("marketplaces", {})
    plugins = data.setdefault("plugins", {})
    if not isinstance(marketplaces, dict) or not isinstance(plugins, dict):
        raise ValueError("marketplaces and plugins must be tables")
    for name, raw in cast(dict[str, Any], marketplaces).items():
        source = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
        if (
            len(source) != 1
            or not set(source) <= set(MARKETPLACE_KINDS)
            or not all(isinstance(value, str) and value for value in source.values())
        ):
            raise ValueError(
                f"marketplace {name} needs exactly one of {list(MARKETPLACE_KINDS)}"
            )
    for plugin_id, raw in cast(dict[str, Any], plugins).items():
        _, at, marketplace = plugin_id.partition("@")
        if not at or marketplace not in marketplaces:
            raise ValueError(f"plugin {plugin_id} must name a declared marketplace")
        if not isinstance(raw, dict) or set(cast(dict[str, Any], raw)) != {"harnesses"}:
            raise ValueError(f"plugin {plugin_id} takes only harnesses")
        harnesses = cast(dict[str, Any], raw)["harnesses"]
        if (
            not isinstance(harnesses, list)
            or not harnesses
            or not set(cast(list[Any], harnesses)) <= set(HARNESSES)
        ):
            raise ValueError(f"plugin {plugin_id} harnesses must be within {HARNESSES}")


def declared(data: dict[str, Any], harness: str) -> list[str]:
    return [
        plugin_id
        for plugin_id, plugin in data["plugins"].items()
        if harness in plugin["harnesses"]
    ]


def _json(command: list[str]) -> Any:
    return json.loads(
        subprocess.run(command, check=True, capture_output=True, text=True).stdout
    )


class _Claude:
    def installed(self) -> set[str]:
        return {
            item["id"]
            for item in _json(["claude", "plugin", "list", "--json"])
            if item["scope"] == "user"
        }

    def marketplaces(self) -> set[str]:
        return {
            item["name"]
            for item in _json(["claude", "plugin", "marketplace", "list", "--json"])
        }

    def add_marketplace(self, source: dict[str, str]) -> list[str]:
        location = source.get("github") or source["git"]
        return ["claude", "plugin", "marketplace", "add", location]

    def install(self, plugin_id: str) -> list[str]:
        return ["claude", "plugin", "install", plugin_id, "--scope", "user"]

    def uninstall(self, plugin_id: str) -> list[str]:
        return ["claude", "plugin", "uninstall", plugin_id, "--scope", "user"]


class _Codex:
    def installed(self) -> set[str]:
        return {
            item["pluginId"]
            for item in _json(["codex", "plugin", "list", "--json"])["installed"]
        }

    def marketplaces(self) -> set[str]:
        listing = _json(["codex", "plugin", "marketplace", "list", "--json"])
        return {item["name"] for item in listing["marketplaces"]}

    def add_marketplace(self, source: dict[str, str]) -> list[str]:
        location = (
            f"https://github.com/{source['github']}.git"
            if "github" in source
            else source["git"]
        )
        return ["codex", "plugin", "marketplace", "add", location]

    def install(self, plugin_id: str) -> list[str]:
        return ["codex", "plugin", "add", plugin_id]

    def uninstall(self, plugin_id: str) -> list[str]:
        return ["codex", "plugin", "remove", plugin_id]


MANAGERS = {"claude": _Claude(), "codex": _Codex()}


def _read_owned(path: Path) -> set[str]:
    if not path.exists():
        return set()
    value = json.loads(path.read_text())
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.partition(":")[0] in HARNESSES
        for item in cast(list[Any], value)
    ):
        raise ValueError(f"{path}: invalid ownership manifest")
    return set(cast(list[str], value))


def reconcile(
    *, home: Path, data: dict[str, Any], harnesses: list[str], check: bool
) -> bool:
    """Bring each targeted harness's plugins to the declaration; return whether any drifted.

    Runs before rendering, because the harnesses' own commands rewrite the settings files the
    renderers then own. A declared plugin is owned whether this reconcile or something
    earlier installed it, so retiring its declaration uninstalls it; others are left alone.
    """
    ownership = home / OWNERSHIP
    owned = _read_owned(ownership)
    changed = False
    for harness in (name for name in HARNESSES if name in harnesses):
        manager = MANAGERS[harness]
        desired = declared(data, harness)
        installed = manager.installed()
        retired = sorted(
            plugin_id
            for item in owned
            for owner, _, plugin_id in [item.partition(":")]
            if owner == harness and plugin_id not in desired and plugin_id in installed
        )
        missing = [plugin_id for plugin_id in desired if plugin_id not in installed]
        known: set[str] = manager.marketplaces() if missing else set()
        needed = sorted({plugin_id.partition("@")[2] for plugin_id in missing} - known)
        commands = [
            *(manager.add_marketplace(data["marketplaces"][name]) for name in needed),
            *(manager.install(plugin_id) for plugin_id in missing),
            *(manager.uninstall(plugin_id) for plugin_id in retired),
        ]
        changed |= bool(commands)
        for command in commands:
            if check:
                print("would run " + " ".join(command))
            else:
                subprocess.run(command, check=True)
        owned = {item for item in owned if item.partition(":")[0] != harness} | {
            f"{harness}:{plugin_id}" for plugin_id in desired
        }
    if not check:
        ownership.parent.mkdir(parents=True, exist_ok=True)
        ownership.write_text(json.dumps(sorted(owned), indent=2) + "\n")
        ownership.chmod(0o600)
    return changed
