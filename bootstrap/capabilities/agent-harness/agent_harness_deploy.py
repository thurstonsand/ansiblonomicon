#!/usr/bin/env python3
"""Reconcile one host's declared agent harness resources through native mise."""

import argparse
import copy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tomllib
from typing import Any, cast

import tomlkit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalogue
from catalogue import FileMetadata, NativeResource, SourceConfig

LEGACY_MANIFESTS = {
    "personal": "macos-managed-files.json",
    "pod042": "pod042-managed-files.json",
}
MANIFEST = LEGACY_MANIFESTS["personal"]


def checkout_for(source: SourceConfig, cache: Path) -> Path:
    return cache / catalogue.filters.agent_harness_repo_to_cache_name(source["repo"])


def source_owner(source: SourceConfig, plugin: dict[str, Any]) -> str:
    origin = str(source.get("repo") or source.get("local"))
    return f"{origin}\0{plugin['name']}"


def declared_owners(sources: list[SourceConfig]) -> tuple[set[str], set[str]]:
    enabled: set[str] = set()
    removed: set[str] = set()
    for source in sources:
        for raw in source.get("plugins", []):
            plugin = cast(dict[str, Any], raw)
            owner = source_owner(source, plugin)
            (removed if plugin.get("remove", False) else enabled).add(owner)
    contradictory = enabled & removed
    if contradictory:
        raise ValueError(
            "Plugin declared both enabled and removed: "
            + ", ".join(sorted(contradictory))
        )
    return enabled, removed


def sync_sources(
    sources: list[SourceConfig], cache: Path, now: float, update: str = "86400s"
) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    interval = None if update == "always" else int(update.removesuffix("s"))
    for source in sources:
        plugins = [p for p in source.get("plugins", []) if not p.get("remove", False)]
        if "repo" not in source or not plugins:
            continue
        checkout = checkout_for(source, cache)
        stamp = checkout.with_name(checkout.name + ".last_update")
        origin = source["repo"]
        url = origin if ":" in origin else f"https://github.com/{origin}.git"
        if not (checkout / ".git").is_dir():
            with tempfile.TemporaryDirectory(
                prefix=f".{checkout.name}.clone-", dir=cache
            ) as temporary:
                candidate = Path(temporary) / checkout.name
                subprocess.run(
                    ["git", "clone", "--depth=1", url, str(candidate)], check=True
                )
                candidate.rename(checkout)
            stamp.touch()
        elif (
            interval is None
            or not stamp.exists()
            or now - stamp.stat().st_mtime >= interval
        ):
            subprocess.run(
                ["git", "-C", str(checkout), "pull", "--ff-only"], check=True
            )
            stamp.touch()


def require_cached_sources(sources: list[SourceConfig], cache: Path) -> None:
    missing = [
        checkout_for(source, cache)
        for source in sources
        if "repo" in source
        and any(not p.get("remove", False) for p in source.get("plugins", []))
        and not (checkout_for(source, cache) / ".git").is_dir()
    ]
    if missing:
        raise ValueError(
            "Missing required cached harness sources: " + ", ".join(map(str, missing))
        )


@dataclass(frozen=True)
class HostConfig:
    profile: str
    hostname: str
    enabled: list[str]
    explicit_only: list[str]
    trim_blocks: bool
    update: str
    manifest: str


def load_host(path: Path) -> HostConfig:
    raw = tomllib.loads(path.read_text()).get("agent_harness")
    if not isinstance(raw, dict):
        raise ValueError(f"Missing [agent_harness] in {path}")
    values = cast(dict[object, object], raw)
    required = {
        "profile": str,
        "hostname": str,
        "enabled": list,
        "explicit_only": list,
        "trim_blocks": bool,
        "update": str,
        "manifest": str,
    }
    for key, expected in required.items():
        if not isinstance(values.get(key), expected):
            raise ValueError(f"Invalid agent_harness.{key} in {path}")
    enabled = cast(list[object], values["enabled"])
    explicit = cast(list[object], values["explicit_only"])
    if not all(isinstance(item, str) for item in enabled) or not all(
        isinstance(item, str) for item in explicit
    ):
        raise ValueError(f"Invalid agent_harness harness lists in {path}")
    return HostConfig(
        profile=cast(str, values["profile"]),
        hostname=cast(str, values["hostname"]),
        enabled=cast(list[str], enabled),
        explicit_only=cast(list[str], explicit),
        trim_blocks=cast(bool, values["trim_blocks"]),
        update=cast(str, values["update"]),
        manifest=cast(str, values["manifest"]),
    )


def roots_for(
    repo: Path, home: Path, cache: Path, profile: str, hostname: str
) -> tuple[Path, ...]:
    _, _, layouts, _ = catalogue.declarations(repo, home, profile, hostname)
    roots = {cache / "hooks"}
    for layout in layouts.values():
        roots.add(Path(layout["skills_dir"]))
        agents = layout["agents_dir"]
        if agents is not None:
            roots.add(Path(agents))
    for declaration in (repo / "bootstrap/capabilities/agent-harness/harnesses").glob(
        "*/mise.toml"
    ):
        document = tomllib.loads(declaration.read_text())
        native = dict(document.get("dotfiles", {}))
        native.update(document.get("bootstrap", {}).get("files", {}))
        for destination in native:
            path = Path(destination.replace("~", str(home), 1))
            if not path.is_absolute():
                path = home / path
            roots.add(path.parent)
    return tuple(sorted(roots))


def validate_destination(
    path: Path,
    home: Path,
    roots: tuple[Path, ...],
    allowed_exact: set[Path] | None = None,
) -> None:
    normalized = Path(os.path.normpath(path))
    if normalized != path:
        raise ValueError(f"Managed path escapes through traversal: {path}")
    if not path.is_absolute() or path == home or not path.is_relative_to(home):
        raise ValueError(f"Managed path escapes operator home: {path}")
    if path not in (allowed_exact or set()) and not any(
        path != root and path.is_relative_to(root) for root in roots
    ):
        raise ValueError(f"Managed path is outside declared harness roots: {path}")
    parent = path.parent
    while parent != home:
        if parent.is_symlink():
            raise ValueError(f"Managed path has a symlink ancestor: {path}")
        parent = parent.parent


def validate_native_destinations(
    native: list[NativeResource], home: Path, roots: tuple[Path, ...]
) -> None:
    destinations: set[Path] = set()
    for resource in native:
        path = resource["destination"]
        validate_destination(path, home, roots)
        if path in destinations:
            raise ValueError(f"Conflicting native harness destination: {path}")
        destinations.add(path)


def load_inventory(
    path: Path,
) -> tuple[dict[str, list[str]], dict[str, str], bool]:
    if path.is_symlink():
        raise ValueError(f"Harness ownership manifest must not be a symlink: {path}")
    if not path.exists():
        return {}, {}, False
    try:
        value = cast(object, json.loads(path.read_text()))
    except json.JSONDecodeError as error:
        raise ValueError(f"Malformed harness ownership manifest: {path}") from error
    if isinstance(value, list):
        legacy = cast(list[object], value)
        if not all(isinstance(item, str) for item in legacy):
            raise ValueError(f"Malformed harness ownership manifest: {path}")
        return {"legacy": cast(list[str], legacy)}, {}, True
    if not isinstance(value, dict):
        raise ValueError(f"Malformed harness ownership manifest: {path}")
    document = cast(dict[object, object], value)
    version = document.get("version")
    if version not in (2, 3):
        raise ValueError(f"Malformed harness ownership manifest: {path}")
    plugins = document.get("plugins")
    if not isinstance(plugins, dict):
        raise ValueError(f"Malformed harness ownership manifest: {path}")
    plugin_map = cast(dict[object, object], plugins)
    for key, paths in plugin_map.items():
        if not isinstance(key, str) or not isinstance(paths, list):
            raise ValueError(f"Malformed harness ownership manifest: {path}")
        entries = cast(list[object], paths)
        if not all(isinstance(entry, str) for entry in entries):
            raise ValueError(f"Malformed harness ownership manifest: {path}")
    proofs: dict[str, str] = {}
    if version == 3:
        raw_proofs = document.get("selection_proofs")
        if not isinstance(raw_proofs, dict):
            raise ValueError(f"Malformed harness ownership manifest: {path}")
        proof_map = cast(dict[object, object], raw_proofs)
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in proof_map.items()
        ):
            raise ValueError(f"Malformed harness ownership manifest: {path}")
        proofs = cast(dict[str, str], proof_map)
    return cast(dict[str, list[str]], plugin_map), proofs, False


def write_inventory(
    path: Path, plugins: dict[str, list[str]], selection_proofs: dict[str, str]
) -> None:
    content = (
        json.dumps(
            {
                "version": 3,
                "plugins": {k: sorted(v) for k, v in sorted(plugins.items())},
                "selection_proofs": dict(sorted(selection_proofs.items())),
            },
            indent=2,
        )
        + "\n"
    )
    if path.exists() and path.read_text() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    candidate = Path(temporary)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        candidate.replace(path)
    finally:
        candidate.unlink(missing_ok=True)


def native_env(target: Path, state: Path) -> dict[str, str]:
    return {
        "HOME": os.environ.get("HOME", ""),
        "PATH": os.environ.get("PATH", ""),
        "MISE_STATE_DIR": str(state),
        "MISE_CEILING_PATHS": str(target.parent),
        "MISE_TRUSTED_CONFIG_PATHS": str(target),
        "MISE_GLOBAL_CONFIG_FILE": str(target / ".global.toml"),
        "MISE_SYSTEM_CONFIG_FILE": str(target / ".system.toml"),
    }


def stage_native(
    target: Path,
    files: dict[Path, tuple[bytes, int]],
    metadata: dict[Path, FileMetadata],
    stale: set[Path],
    rendered: Path,
    native: list[NativeResource],
) -> None:
    rendered.mkdir(parents=True, exist_ok=True)
    document: dict[str, object] = {
        "min_version": "2026.9.11",
        "vars": {},
        "dotfiles": {},
        "bootstrap": {"files": {}},
    }
    variables = cast(dict[str, object], document["vars"])
    dotfiles = cast(dict[str, object], document["dotfiles"])
    bootstrap = cast(dict[str, object], document["bootstrap"])
    native_files = cast(dict[str, object], bootstrap["files"])
    for index, (destination, (content, mode)) in enumerate(sorted(files.items())):
        detail = metadata[destination]
        if detail["mode"] == "symlink":
            source = Path(cast(str, detail["source"]))
        else:
            source = rendered / str(index)
            if not source.exists() or source.read_bytes() != content:
                source.write_bytes(content)
            if source.stat().st_mode & 0o777 != mode:
                source.chmod(mode)
        dotfiles[str(destination)] = {"source": str(source), "mode": detail["mode"]}
    for resource in native:
        destination = str(resource["destination"])
        resource_table = dotfiles if resource["kind"] == "dotfiles" else native_files
        resource_table[destination] = resource["declaration"]
        for key, value in resource["variables"].items():
            if key in variables and variables[key] != value:
                raise ValueError(f"Conflicting native harness variable: {key}")
            variables[key] = value
    for destination in sorted(stale):
        if str(destination) not in native_files:
            native_files[str(destination)] = {"state": "absent"}
    config = tomlkit.dumps(document)
    config_path = target / "mise.toml"
    if not config_path.exists() or config_path.read_text() != config:
        config_path.write_text(config)


def apply_native(target: Path, state: Path, check: bool) -> None:
    env = native_env(target, state)
    flags = ["--force", "--dry-run"] if check else ["--force", "--yes"]
    subprocess.run(
        ["mise", "-C", str(target), "bootstrap", "dotfiles", "apply", *flags],
        check=True,
        env=env,
    )
    file_flags = ["--dry-run"] if check else ["--yes"]
    subprocess.run(
        ["mise", "-C", str(target), "bootstrap", "files", "apply", *file_flags],
        check=True,
        env=env,
    )


def repair_copy_modes(
    files: dict[Path, tuple[bytes, int]], metadata: dict[Path, FileMetadata]
) -> None:
    """Enforce output modes that mise dotfiles copy does not reconcile."""
    for destination, (_, mode) in files.items():
        if metadata[destination]["mode"] != "copy":
            continue
        if destination.is_symlink() or not destination.is_file():
            raise ValueError(
                f"Native apply did not create a regular file: {destination}"
            )
        if destination.stat().st_mode & 0o777 != mode:
            destination.chmod(mode, follow_symlinks=False)


def reconcile(
    repo: Path,
    home: Path,
    cache: Path,
    profile: str,
    hostname: str,
    *,
    check: bool,
    cached: bool,
    update: str = "86400s",
    manifest_name: str | None = None,
    enabled_harnesses: list[str] | None = None,
    explicit_only: list[str] | None = None,
    trim_blocks: bool | None = None,
) -> None:
    repo, home, cache = map(Path.resolve, (repo, home, cache))
    if not cache.is_relative_to(home):
        raise ValueError("Harness cache must be inside operator home")
    _, selected_profile, _, sources = catalogue.declarations(
        repo, home, profile, hostname
    )
    selected_harnesses = (
        selected_profile["target_agents"]
        if enabled_harnesses is None
        else enabled_harnesses
    )
    native = catalogue.native_resources(repo, home, selected_harnesses)
    enabled, removed = declared_owners(sources)
    manifest = cache / (
        manifest_name or LEGACY_MANIFESTS.get(profile, f"{profile}-managed-files.json")
    )
    inventory, selection_proofs, _legacy = load_inventory(manifest)
    fingerprints = catalogue.selection_fingerprints(sources)
    roots = roots_for(repo, home, cache, profile, hostname)
    validate_native_destinations(native, home, roots)
    previous_paths = {
        owner: [home / item for item in paths] for owner, paths in inventory.items()
    }
    recorded_native_paths = {
        path
        for owner, paths in previous_paths.items()
        if owner.startswith("native:")
        for path in paths
    }
    # A real pre-v2 manifest is an unowned list. Adopt paths that are still
    # declared before enforcing exclusive ownership, and preserve the rest.
    native_owner = {
        item["destination"]: item["owner"]
        for item in native
        if item["declaration"].get("state", "present") != "absent"
    }
    if "legacy" in previous_paths:
        legacy_paths = previous_paths.pop("legacy")
        cached_checkouts_complete = all(
            "repo" not in source
            or not any(not p.get("remove", False) for p in source.get("plugins", []))
            or (checkout_for(source, cache) / ".git").is_dir()
            for source in sources
        )
        if not cached_checkouts_complete:
            raise ValueError(
                "Cannot migrate legacy harness ownership without cached sources"
            )
        legacy_metadata: dict[Path, FileMetadata] = {}
        catalogue.render_files(
            repo,
            home,
            cache,
            profile,
            hostname,
            trim_blocks=(profile == "personal") if trim_blocks is None else trim_blocks,
            metadata=legacy_metadata,
            enabled_harnesses=enabled_harnesses,
            explicit_only=explicit_only,
        )
        old_owner = {path: detail["owner"] for path, detail in legacy_metadata.items()}
        for path in legacy_paths:
            previous_paths.setdefault(
                native_owner.get(path, old_owner.get(path, "legacy-unmapped")), []
            ).append(path)
    retained_owner: dict[Path, str] = {}
    for owner, paths in previous_paths.items():
        for path in paths:
            prior = retained_owner.setdefault(path, owner)
            if prior != owner:
                raise ValueError(
                    f"Malformed harness ownership manifest shares {path}: {prior!r} and {owner!r}"
                )
    for paths in previous_paths.values():
        for path in paths:
            validate_destination(path, home, roots, recorded_native_paths)
            if path.is_dir() and not path.is_symlink():
                raise ValueError(
                    f"Manifest-owned file was replaced by a directory: {path}"
                )
    if _legacy and not check:
        write_inventory(
            manifest,
            {
                owner: [str(path.relative_to(home)) for path in paths]
                for owner, paths in previous_paths.items()
            },
            selection_proofs,
        )
    unproved_retained = (enabled & previous_paths.keys()) - selection_proofs.keys()
    if unproved_retained:
        # A v2 inventory proves ownership only.  Validate its still-cached
        # declarations before Git can remove a named selection, then persist
        # that proof as the migration baseline.
        baseline_sources: list[SourceConfig] = []
        for source in sources:
            baseline_plugins = [
                plugin
                for plugin in source.get("plugins", [])
                if source_owner(source, cast(dict[str, Any], plugin))
                in unproved_retained
            ]
            if baseline_plugins:
                baseline_source = copy.copy(source)
                baseline_source["plugins"] = baseline_plugins
                baseline_sources.append(baseline_source)
        catalogue.filters.agent_harness_build_plugin_resources(
            baseline_sources, str(cache)
        )
        selection_proofs.update(
            {owner: fingerprints[owner] for owner in unproved_retained}
        )
        if not check:
            write_inventory(
                manifest,
                {
                    owner: [str(path.relative_to(home)) for path in paths]
                    for owner, paths in previous_paths.items()
                },
                selection_proofs,
            )
    if check or cached:
        require_cached_sources(sources, cache)
    else:
        cached_checkouts_complete = all(
            "repo" not in source
            or not any(not p.get("remove", False) for p in source.get("plugins", []))
            or (checkout_for(source, cache) / ".git").is_dir()
            for source in sources
        )
        if not manifest.exists() and cached_checkouts_complete:
            old_metadata: dict[Path, FileMetadata] = {}
            old_files = catalogue.render_files(
                repo,
                home,
                cache,
                profile,
                hostname,
                trim_blocks=(profile == "personal")
                if trim_blocks is None
                else trim_blocks,
                metadata=old_metadata,
                enabled_harnesses=enabled_harnesses,
                explicit_only=explicit_only,
            )
            adopted: dict[str, list[str]] = {}
            for path, (content, mode) in old_files.items():
                equivalent = (
                    path.is_file()
                    and not path.is_symlink()
                    and path.read_bytes() == content
                    and path.stat().st_mode & 0o777 == mode
                )
                correct_link = (
                    path.is_symlink()
                    and old_metadata[path]["mode"] == "symlink"
                    and path.resolve()
                    == Path(cast(str, old_metadata[path]["source"])).resolve()
                )
                if equivalent or correct_link:
                    validate_destination(path, home, roots)
                    adopted.setdefault(old_metadata[path]["owner"], []).append(
                        str(path.relative_to(home))
                    )
            if adopted:
                adopted_proofs = dict(selection_proofs)
                adopted_proofs.update(
                    {
                        owner: fingerprints[owner]
                        for owner in adopted
                        if owner in fingerprints
                    }
                )
                write_inventory(manifest, adopted, adopted_proofs)
                selection_proofs = adopted_proofs
                inventory = adopted
                previous_paths = {
                    owner: [home / item for item in paths]
                    for owner, paths in inventory.items()
                }
        sync_sources(sources, cache, time.time(), update)
    allowed_missing = {
        owner
        for owner, fingerprint in fingerprints.items()
        if selection_proofs.get(owner) == fingerprint
    }
    metadata: dict[Path, FileMetadata] = {}
    files = catalogue.render_files(
        repo,
        home,
        cache,
        profile,
        hostname,
        trim_blocks=(profile == "personal") if trim_blocks is None else trim_blocks,
        metadata=metadata,
        enabled_harnesses=enabled_harnesses,
        explicit_only=explicit_only,
        allow_missing_selections=allowed_missing,
    )
    for resource in native:
        path = resource["destination"]
        state = resource["declaration"].get("state", "present")
        if state == "absent":
            desired_detail = metadata.get(path)
            if desired_detail is not None:
                raise ValueError(
                    f"Native absence {path} conflicts with desired owner "
                    f"{desired_detail['owner']!r}"
                )
            retained = retained_owner.get(path)
            if retained is not None and retained != resource["owner"]:
                raise ValueError(
                    f"Native absence {path} is retained by {retained!r}, "
                    f"not {resource['owner']!r}"
                )
            continue
        if path in metadata:
            raise ValueError(f"Conflicting harness destination: {path}")
        metadata[path] = {
            "owner": resource["owner"],
            "source": None,
            "mode": "native",
        }
    remove_sources: list[SourceConfig] = []
    for source in sources:
        plugins: list[dict[str, Any]] = []
        for raw in source.get("plugins", []):
            if raw.get("remove", False):
                plugin = dict(raw)
                plugin["remove"] = False
                plugins.append(plugin)
        if plugins:
            candidate = copy.deepcopy(source)
            candidate["plugins"] = plugins
            remove_sources.append(candidate)
    resolved_remove: dict[str, list[Path]] = {}
    for remove_source in remove_sources:
        owners = {
            source_owner(remove_source, cast(dict[str, Any], plugin))
            for plugin in remove_source.get("plugins", [])
        }
        unresolved = owners - previous_paths.keys()
        if not unresolved:
            continue
        if (
            "repo" in remove_source
            and not (checkout_for(remove_source, cache) / ".git").is_dir()
        ):
            raise ValueError(
                "Cannot remove without retained inventory or cached source: "
                + ", ".join(sorted(unresolved))
            )
        unresolved_source = copy.deepcopy(remove_source)
        unresolved_source["plugins"] = [
            plugin
            for plugin in remove_source.get("plugins", [])
            if source_owner(remove_source, cast(dict[str, Any], plugin)) in unresolved
        ]
        remove_metadata: dict[Path, FileMetadata] = {}
        catalogue.render_files(
            repo,
            home,
            cache,
            profile,
            hostname,
            trim_blocks=(profile == "personal") if trim_blocks is None else trim_blocks,
            metadata=remove_metadata,
            enabled_harnesses=enabled_harnesses,
            explicit_only=explicit_only,
            sources_override=[unresolved_source],
        )
        for path, detail in remove_metadata.items():
            validate_destination(path, home, roots)
            retained = retained_owner.get(path)
            if retained is not None and retained != detail["owner"]:
                raise ValueError(
                    f"Resolved removal {path} is retained by {retained!r}, "
                    f"not {detail['owner']!r}"
                )
            resolved_remove.setdefault(detail["owner"], []).append(path)
    for owner in removed:
        if owner not in previous_paths and owner not in resolved_remove:
            raise ValueError(
                f"Cannot remove {owner!r}: no retained inventory or resolvable declaration"
            )
        previous_paths.setdefault(owner, []).extend(resolved_remove.get(owner, []))
    for path in files:
        validate_destination(path, home, roots)
    destination_owners: dict[Path, str] = {}
    for path, detail in metadata.items():
        prior = destination_owners.setdefault(path, detail["owner"])
        if prior != detail["owner"]:
            raise ValueError(
                f"Conflicting ownership for destination {path}: {prior!r} and {detail['owner']!r}"
            )
    for path in list(previous_paths.get("legacy-unmapped", [])):
        owner = destination_owners.get(path)
        if owner:
            previous_paths["legacy-unmapped"].remove(path)
            previous_paths.setdefault(owner, []).append(path)
            retained_owner[path] = owner
    for path, detail in metadata.items():
        retained = retained_owner.get(path)
        if retained is not None and retained != detail["owner"]:
            raise ValueError(
                f"Destination {path} is retained by {retained!r}, not {detail['owner']!r}"
            )
    desired: dict[str, list[Path]] = {}
    for path, detail in metadata.items():
        desired.setdefault(detail["owner"], []).append(path)
    known_owned = {path for paths in previous_paths.values() for path in paths}
    for path, (content, mode) in files.items():
        if not path.exists() and not path.is_symlink():
            continue
        equivalent = (
            path.is_file()
            and not path.is_symlink()
            and path.read_bytes() == content
            and path.stat().st_mode & 0o777 == mode
        )
        correct_link = (
            path.is_symlink()
            and metadata[path]["mode"] == "symlink"
            and path.resolve() == Path(cast(str, metadata[path]["source"])).resolve()
        )
        if path not in known_owned and not equivalent and not correct_link:
            raise ValueError(f"Refusing to overwrite unrelated path: {path}")
    for resource in native:
        path = resource["destination"]
        if resource["declaration"].get("state", "present") == "absent":
            continue
        if (path.exists() or path.is_symlink()) and path not in known_owned:
            raise ValueError(f"Refusing to overwrite unrelated native path: {path}")
    next_inventory = {
        owner: list(paths)
        for owner, paths in previous_paths.items()
        if owner not in removed
    }
    for owner in removed:
        next_inventory[owner] = []
    for owner in enabled:
        next_inventory[owner] = desired.get(owner, [])
    for owner in {f"native:{target}" for target in selected_harnesses}:
        next_inventory[owner] = desired.get(owner, [])
    stale = {
        path
        for owner, paths in previous_paths.items()
        if owner in enabled or owner in removed or owner.startswith("native:")
        for path in paths
        if path not in set(next_inventory.get(owner, []))
    }
    for path in stale:
        validate_destination(path, home, roots, recorded_native_paths)
        owner = destination_owners.get(path)
        retained = retained_owner.get(path)
        if owner is not None and retained is not None and owner != retained:
            raise ValueError(f"Refusing cross-owner stale deletion: {path}")
    serialized = {
        owner: [str(path.relative_to(home)) for path in paths]
        for owner, paths in next_inventory.items()
    }
    pending = {
        owner: sorted(
            {
                *(
                    str(path.relative_to(home))
                    for path in previous_paths.get(owner, [])
                ),
                *serialized.get(owner, []),
            }
        )
        for owner in set(previous_paths) | set(serialized)
        if owner != "legacy"
    }
    if check:
        for path, (_, mode) in files.items():
            if (
                metadata[path]["mode"] == "copy"
                and path.is_file()
                and not path.is_symlink()
                and path.stat().st_mode & 0o777 != mode
            ):
                print(f"Would correct mode on {path} to {mode:04o}")
        with tempfile.TemporaryDirectory(prefix="agent-harness-check-") as temporary:
            target = Path(temporary)
            stage_native(target, files, metadata, stale, target / "rendered", native)
            apply_native(target, target / "mise-state", True)
        return
    target = cache / "native"
    target.mkdir(parents=True, exist_ok=True)
    rendered = cache / "rendered"
    stage_native(target, files, metadata, stale, rendered, native)
    validated_proofs = dict(selection_proofs)
    validated_proofs.update(
        {
            owner: fingerprint
            for owner, fingerprint in fingerprints.items()
            if owner in enabled
        }
    )
    write_inventory(manifest, pending, validated_proofs)
    apply_native(target, cache / "mise-state", False)
    repair_copy_modes(files, metadata)
    stage_native(target, files, metadata, set(), rendered, native)
    write_inventory(manifest, serialized, validated_proofs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--host-config", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--cached", action="store_true")
    args = parser.parse_args()
    host = load_host(args.host_config)
    reconcile(
        args.repo,
        args.home,
        args.cache,
        host.profile,
        host.hostname,
        check=args.check,
        cached=args.cached,
        update=host.update,
        manifest_name=host.manifest,
        enabled_harnesses=host.enabled,
        explicit_only=host.explicit_only,
        trim_blocks=host.trim_blocks,
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"agent-harness: {error}", file=sys.stderr)
        raise SystemExit(1) from error
