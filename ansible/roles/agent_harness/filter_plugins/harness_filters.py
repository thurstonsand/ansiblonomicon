"""Filter plugins for agent_harness role."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, TypedDict, cast


class PluginEntry(TypedDict, total=False):
    """A plugin as declared in the config, before profile resolution."""

    name: str
    target_agents: list[str]
    included_on: list[str]
    excluded_on: list[str]
    skills: dict[str, str]  # explicit {deploy_name: path} map
    agents: dict[str, str]  # explicit {deploy_name: path} map
    include_skills: list[str] | dict[str, list[str]]
    exclude_skills: list[str] | dict[str, list[str]]
    include_agents: list[str] | dict[str, list[str]]
    exclude_agents: list[str] | dict[str, list[str]]
    hooks: bool
    exclude_data: list[str]  # rsync --exclude patterns for deployed files


SourceConfig = dict[str, Any]  # Union of git/local source dicts from Ansible

SOURCE_FIELDS = frozenset({"repo", "local", "included_on", "excluded_on", "plugins"})
PLUGIN_FIELDS = frozenset(
    {
        "name",
        "target_agents",
        "included_on",
        "excluded_on",
        "skills",
        "agents",
        "include_skills",
        "exclude_skills",
        "include_agents",
        "exclude_agents",
        "hooks",
        "exclude_data",
    }
)
RESOURCE_KINDS = ("skills", "agents")
ANY_PROFILE = "*"


@dataclass
class ResourceInfo:
    """A skill or agent resolved to a path on disk."""

    name: str
    source: str
    origin: str
    plugin_root: str = ""
    target_agents: list[str] = field(default_factory=list)
    exclude_data: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for Ansible/Jinja2 compatibility."""
        return {
            "name": self.name,
            "source": self.source,
            "origin": self.origin,
            "plugin_root": self.plugin_root,
            "target_agents": list(self.target_agents),
            "exclude_data": list(self.exclude_data),
        }


@dataclass
class HookFragment:
    """A resolved hook fragment ready for deployment."""

    name: str
    content: str
    plugin_root: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "content": self.content}


@dataclass
class PluginResources:
    """Everything one pass over the resolved sources produced."""

    by_kind: dict[str, list[ResourceInfo]] = field(
        default_factory=lambda: {kind: [] for kind in RESOURCE_KINDS}
    )
    hooks: dict[str, HookFragment] = field(default_factory=dict)

    def add_hooks(self, fragment: HookFragment) -> None:
        """Record a fragment, collapsing duplicates and rejecting conflicts.

        One plugin may legitimately be declared twice (different target_agents),
        which yields the same fragment twice; two different plugins sharing a
        name would silently overwrite each other's cache file instead.
        """
        existing = self.hooks.get(fragment.name)
        if existing is None:
            self.hooks[fragment.name] = fragment
            return
        if existing.content != fragment.content:
            msg = (
                f"plugin {fragment.name}: conflicting hook fragments from "
                f"{existing.plugin_root} and {fragment.plugin_root}"
            )
            raise ValueError(msg)

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        """Convert to dict for Ansible/Jinja2 compatibility."""
        return {
            **{
                kind: [resource.to_dict() for resource in resources]
                for kind, resources in self.by_kind.items()
            },
            "hooks": [fragment.to_dict() for fragment in self.hooks.values()],
        }


@dataclass
class ResolvedPlugin:
    """A plugin after profile resolution, with selections keyed by kind.

    A selection of ``None`` was never declared; an empty list was declared and
    is empty, which for an include means nothing ships.
    """

    name: str
    target_agents: list[str] = field(default_factory=list)
    explicit: dict[str, dict[str, str] | None] = field(default_factory=dict)
    include: dict[str, list[str] | None] = field(default_factory=dict)
    exclude: dict[str, list[str] | None] = field(default_factory=dict)
    hooks: bool = True
    exclude_data: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, plugin: Mapping[str, Any]) -> ResolvedPlugin:
        """Read back a plugin dict produced by agent_harness_resolve_sources."""
        return cls(
            name=plugin["name"],
            target_agents=list(plugin.get("target_agents", [])),
            explicit={
                kind: dict(plugin[kind]) if plugin.get(kind) is not None else None
                for kind in RESOURCE_KINDS
            },
            include={
                kind: _optional_list(plugin.get(f"include_{kind}"))
                for kind in RESOURCE_KINDS
            },
            exclude={
                kind: _optional_list(plugin.get(f"exclude_{kind}"))
                for kind in RESOURCE_KINDS
            },
            hooks=plugin.get("hooks", True),
            exclude_data=list(plugin.get("exclude_data", [])),
        )

    @property
    def explicit_mode(self) -> bool:
        """An explicit map for either kind takes the whole plugin off manifests."""
        return any(self.explicit[kind] is not None for kind in RESOURCE_KINDS)


def _optional_list(value: Any) -> list[str] | None:
    return None if value is None else [str(entry) for entry in cast(list[Any], value)]


def _repo_to_cache_name(repo: str) -> str:
    """Normalize a repo identifier into a filesystem-safe cache directory name.

    Handles both short form (owner/name) and full URLs (https:// or git@).
    """
    name = repo
    name = re.sub(r"^https?://", "", name)
    name = re.sub(r"^git@", "", name)
    name = re.sub(r"\.git$", "", name)
    name = re.sub(r"[/:.]+", "--", name)
    name = re.sub(r"-{2,}", "--", name)
    return name.strip("-")


# =============================================================================
# Profile resolution: config in, concrete per-profile config out
# =============================================================================


def _source_label(source: Mapping[str, Any]) -> str:
    return str(source.get("repo") or source.get("local") or source)


def _reject_unknown_fields(
    entry: Mapping[str, Any], known: frozenset[str], label: str
) -> None:
    unknown = sorted(set(entry) - known)
    if unknown:
        msg = f"{label}: unknown field(s) {', '.join(unknown)}"
        raise ValueError(msg)


def _require_string_list(value: Any, label: str, field_name: str) -> list[str]:
    """Accept only a real list of strings; a bare string is an error, not an iterable."""
    if isinstance(value, str) or not isinstance(value, Sequence):
        msg = f"{label}: {field_name} must be a list of strings, got {value!r}"
        raise ValueError(msg)
    entries = list(cast(Sequence[Any], value))
    for entry in entries:
        if not isinstance(entry, str):
            msg = f"{label}: {field_name} entries must be strings, got {entry!r}"
            raise ValueError(msg)
    return cast(list[str], entries)


def _require_bool(value: Any, label: str, field_name: str) -> bool:
    if not isinstance(value, bool):
        msg = f"{label}: {field_name} must be true or false, got {value!r}"
        raise ValueError(msg)
    return value


def _require_known(
    entries: list[str], known: set[str], label: str, field_name: str, noun: str
) -> list[str]:
    for entry in entries:
        if entry not in known:
            msg = (
                f"{label}: {field_name} names unknown {noun} {entry!r} "
                f"(known: {', '.join(sorted(known))})"
            )
            raise ValueError(msg)
    return entries


def _require_string_map(value: Any, label: str, field_name: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        msg = f"{label}: {field_name} must be a {{name: path}} map, got {value!r}"
        raise ValueError(msg)
    resolved: dict[str, str] = {}
    for key, entry in cast(Mapping[Any, Any], value).items():
        if not isinstance(key, str) or not isinstance(entry, str):
            msg = (
                f"{label}: {field_name} must map strings to paths, "
                f"got {key!r}: {entry!r}"
            )
            raise ValueError(msg)
        resolved[key] = entry
    return resolved


def _as_plugin_mapping(plugin: Any, source_label: str) -> Mapping[str, Any]:
    """Conform an untrusted plugin entry from YAML into a mapping."""
    if not isinstance(plugin, Mapping):
        msg = f"{source_label}: plugin entry must be a mapping, got {plugin!r}"
        raise ValueError(msg)
    return cast(Mapping[str, Any], plugin)


def _profile_admits(
    entry: Mapping[str, Any], profile: str, profile_names: set[str], label: str
) -> bool:
    """Validate the profile scoping of a source or plugin and apply it."""
    scope: dict[str, list[str]] = {}
    for field_name in ("included_on", "excluded_on"):
        if field_name in entry:
            entries = _require_string_list(entry[field_name], label, field_name)
            scope[field_name] = _require_known(
                entries, profile_names, label, field_name, "profile"
            )
    included_on = scope.get("included_on", [])
    if included_on and profile not in included_on:
        return False
    return profile not in scope.get("excluded_on", [])


def _collapse_selection(
    spec: Any, profile: str, profile_names: set[str], label: str, field_name: str
) -> list[str] | None:
    """Reduce a selection list or profile-keyed map to this profile's list.

    A profile key fully replaces the ``"*"`` fallback; the two never merge.
    ``None`` means the field was never declared, so nothing is filtered; an
    empty list means it was declared and selects nothing.
    """
    if spec is None:
        return None
    if isinstance(spec, Mapping):
        selected = cast(Mapping[str, Any], spec)
        keys = list(selected)
        for index, key in enumerate(keys):
            if key == ANY_PROFILE:
                if index != len(keys) - 1:
                    msg = (
                        f"{label}: {field_name} lists {ANY_PROFILE!r} before "
                        f"{keys[index + 1]!r}; the fallback must come last"
                    )
                    raise ValueError(msg)
            elif key not in profile_names:
                msg = f"{label}: {field_name} names unknown profile {key!r}"
                raise ValueError(msg)
            _require_string_list(selected[key], label, f"{field_name}[{key}]")
        if profile in selected:
            return list(cast(list[str], selected[profile]))
        if ANY_PROFILE in selected:
            return list(cast(list[str], selected[ANY_PROFILE]))
        return []
    if isinstance(spec, Sequence) and not isinstance(spec, str):
        return _require_string_list(spec, label, field_name)
    msg = f"{label}: {field_name} must be a list or a profile-keyed map, got {spec!r}"
    raise ValueError(msg)


def _resolve_plugin(
    plugin: Mapping[str, Any],
    profile: str,
    profile_names: set[str],
    harness_names: set[str],
    source_label: str,
) -> dict[str, Any] | None:
    """Validate one plugin entry and collapse it for a single profile."""
    name = plugin.get("name")
    if not name or not isinstance(name, str):
        msg = f"{source_label}: plugin entry is missing a name: {dict(plugin)!r}"
        raise ValueError(msg)

    label = f"{source_label}: plugin {name}"
    _reject_unknown_fields(plugin, PLUGIN_FIELDS, label)
    explicit_kinds = [kind for kind in RESOURCE_KINDS if plugin.get(kind) is not None]

    resolved: dict[str, Any] = {"name": name}
    for kind in RESOURCE_KINDS:
        explicit = plugin.get(kind)
        selections = {
            f"{selector}_{kind}": _collapse_selection(
                plugin.get(f"{selector}_{kind}"),
                profile,
                profile_names,
                label,
                f"{selector}_{kind}",
            )
            for selector in ("include", "exclude")
        }
        declared = [
            field_name
            for field_name, selection in selections.items()
            if selection is not None
        ]

        if len(declared) == 2:
            msg = f"{label}: include_{kind} and exclude_{kind} are mutually exclusive"
            raise ValueError(msg)
        if explicit is not None and declared:
            msg = (
                f"{label}: the explicit {kind} map already selects resources; "
                f"drop include_{kind}/exclude_{kind}"
            )
            raise ValueError(msg)
        if explicit_kinds and declared:
            msg = (
                f"{label}: the explicit {explicit_kinds[0]} map puts this plugin in "
                f"explicit mode, so there is no manifest to select from; "
                f"drop {declared[0]}"
            )
            raise ValueError(msg)

        if explicit is not None:
            resolved[kind] = _require_string_map(explicit, label, kind)
        resolved.update(
            {
                field_name: selection
                for field_name, selection in selections.items()
                if selection is not None
            }
        )

    if not _profile_admits(plugin, profile, profile_names, label):
        return None

    target_agents = _collapse_selection(
        plugin.get("target_agents"), profile, profile_names, label, "target_agents"
    )
    if target_agents == []:
        # Declared for other profiles only: the plugin serves no harness here.
        return None
    if target_agents is not None:
        resolved["target_agents"] = _require_known(
            target_agents, harness_names, label, "target_agents", "harness"
        )
    if "exclude_data" in plugin:
        resolved["exclude_data"] = _require_string_list(
            plugin["exclude_data"], label, "exclude_data"
        )
    if "hooks" in plugin:
        resolved["hooks"] = _require_bool(plugin["hooks"], label, "hooks")
    return resolved


def agent_harness_resolve_sources(
    sources: list[SourceConfig],
    profile: str,
    profile_names: list[str],
    harness_names: list[str],
    extra_sources: list[SourceConfig] | None = None,
) -> list[SourceConfig]:
    """Validate the declared sources and resolve them for one host profile."""
    known_profiles = set(profile_names)
    known_harnesses = set(harness_names)
    resolved_sources: list[SourceConfig] = []

    for source in [*sources, *(extra_sources or [])]:
        label = f"source {_source_label(source)}"
        _reject_unknown_fields(source, SOURCE_FIELDS, label)
        if ("repo" in source) == ("local" in source):
            msg = f"{label}: declare exactly one of repo or local"
            raise ValueError(msg)
        origin_key = "repo" if "repo" in source else "local"
        if not source[origin_key] or not isinstance(source[origin_key], str):
            msg = f"{label}: {origin_key} must be a non-empty string"
            raise ValueError(msg)
        plugins = source.get("plugins", [])
        if not isinstance(plugins, Sequence) or isinstance(plugins, str):
            msg = f"{label}: plugins must be a list, got {plugins!r}"
            raise ValueError(msg)

        resolved_plugins = [
            resolved
            for plugin in cast(Sequence[Any], plugins)
            if (
                resolved := _resolve_plugin(
                    _as_plugin_mapping(plugin, label),
                    profile,
                    known_profiles,
                    known_harnesses,
                    label,
                )
            )
        ]
        if not _profile_admits(source, profile, known_profiles, label):
            continue

        resolved_source: dict[str, Any] = {origin_key: source[origin_key]}
        resolved_source["plugins"] = resolved_plugins
        resolved_sources.append(resolved_source)

    return resolved_sources


# =============================================================================
# Filesystem resolution: resolved config in, resources on disk out
# =============================================================================


def _join_within(root: Path, relative: str, label: str, what: str) -> Path:
    """Join an upstream-supplied relative path under a root it may not escape.

    Manifest and marketplace values come from repositories we do not control,
    and the result of this join is what gets rsynced onto the machine.
    """
    candidate = Path(relative)
    if candidate.is_absolute():
        msg = f"{label}: {what} {relative!r} must be relative, not absolute"
        raise ValueError(msg)
    joined = root / candidate
    if not joined.resolve().is_relative_to(root.resolve()):
        msg = f"{label}: {what} {relative!r} escapes {root}"
        raise ValueError(msg)
    return joined


def _load_plugin_json(plugin_path: Path) -> dict[str, Any] | None:
    """Load and parse .claude-plugin/plugin.json from a plugin directory."""
    plugin_json_path = plugin_path / ".claude-plugin" / "plugin.json"
    if not plugin_json_path.exists():
        return None

    try:
        with plugin_json_path.open() as f:
            return json.load(f)  # type: ignore[no-any-return]
    except json.JSONDecodeError, OSError:
        return None


def _find_skill_md(directory: Path) -> Path | None:
    """Find SKILL.md or SKILL.md.j2 in a directory, case-insensitive.

    Returns the path to the skill file if found, or None if not found.
    """
    if not directory.is_dir():
        return None
    for entry in directory.iterdir():
        if entry.is_file() and entry.name.lower() in ("skill.md", "skill.md.j2"):
            return entry
    return None


def _find_in_marketplace(
    repo_path: Path, plugin_name: str, label: str
) -> tuple[Path, dict[str, Any]] | None:
    """Look up a plugin by name in marketplace.json.

    Honours `strict`: strict (the default) merges the plugin's own plugin.json
    under the marketplace entry; strict false makes the entry the whole manifest.
    """
    marketplace_path = repo_path / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.exists():
        return None

    try:
        with marketplace_path.open() as f:
            marketplace = json.load(f)
    except json.JSONDecodeError, OSError:
        return None

    plugin_root = marketplace.get("metadata", {}).get("pluginRoot", "")
    if plugin_root:
        _join_within(repo_path, str(plugin_root), label, "marketplace pluginRoot")

    for entry in marketplace.get("plugins", []):
        if entry.get("name") != plugin_name:
            continue
        source = entry.get("source", "")
        # Dict sources point at another repo; we only resolve in-tree plugins.
        if not isinstance(source, str):
            continue
        if plugin_root and not source.startswith(("./", "/")):
            source = f"{plugin_root}/{source}"
        plugin_path = _join_within(repo_path, source, label, "marketplace source")

        if not entry.get("strict", True):
            return plugin_path, dict(entry)
        plugin_json = _load_plugin_json(plugin_path)
        manifest = {**plugin_json, **entry} if plugin_json else dict(entry)
        return plugin_path, manifest

    return None


def _find_manifest(
    source_root: Path, is_repo: bool, plugin_name: str, label: str
) -> tuple[Path, dict[str, Any]] | None:
    """Locate a plugin's root directory and its Claude manifest."""
    if not is_repo:
        plugin_json = _load_plugin_json(source_root)
        if plugin_json is not None and plugin_json.get("name") == plugin_name:
            return source_root, plugin_json
        return None

    if found := _find_in_marketplace(source_root, plugin_name, label):
        return found

    plugin_json = _load_plugin_json(source_root)
    if plugin_json is not None and plugin_json.get("name") == plugin_name:
        return source_root, plugin_json
    return None


def _manifest_dirs(
    plugin_root: Path, manifest: Mapping[str, Any], kind: str, label: str
) -> list[Path]:
    """Read the manifest's skills/agents paths, defaulting to the conventional dir."""
    declared = manifest.get(kind)
    if declared is None:
        relatives = [kind]
    elif isinstance(declared, str):
        relatives = [declared]
    else:
        relatives = [str(path) for path in cast(list[Any], declared)]
    return [
        _join_within(plugin_root, relative, label, f"manifest {kind} path")
        for relative in relatives
    ]


def _discover_skills(
    plugin_root: Path, plugin_name: str, manifest: Mapping[str, Any], label: str
) -> list[tuple[str, Path]]:
    """Find the skills a manifest exposes, one level deep at most."""
    # A plugin that is itself a skill has no inner skills to enumerate; walking
    # its paths as well would report the same directory twice.
    if _find_skill_md(plugin_root):
        return [(plugin_name, plugin_root)]

    found: list[tuple[str, Path]] = []
    for skills_dir in _manifest_dirs(plugin_root, manifest, "skills", label):
        if not skills_dir.is_dir():
            continue
        if _find_skill_md(skills_dir):
            found.append((skills_dir.name, skills_dir))
            continue
        found.extend(
            (entry.name, entry)
            for entry in sorted(skills_dir.iterdir())
            if _find_skill_md(entry)
        )
    return found


def _discover_agents(
    plugin_root: Path, plugin_name: str, manifest: Mapping[str, Any], label: str
) -> list[tuple[str, Path]]:
    """Find the agent markdown files a manifest exposes."""
    del plugin_name
    found: list[tuple[str, Path]] = []
    for agents_dir in _manifest_dirs(plugin_root, manifest, "agents", label):
        if not agents_dir.is_dir():
            continue
        found.extend(
            (entry.stem, entry)
            for entry in sorted(agents_dir.iterdir())
            if entry.is_file() and entry.suffix == ".md"
        )
    return found


def _apply_selection(
    found: list[tuple[str, Path]],
    include: list[str] | None,
    exclude: list[str] | None,
    label: str,
    kind: str,
) -> list[tuple[str, Path]]:
    """Narrow discovered resources, rejecting selections that match nothing.

    ``None`` means the selector was never declared and nothing is filtered;
    an empty include list ships nothing.
    """
    discovered = {name for name, _ in found}
    for selector, entries in (("include", include), ("exclude", exclude)):
        for entry in entries or []:
            if entry not in discovered:
                msg = (
                    f"{label}: {selector}_{kind} names {entry!r}, which the plugin "
                    f"does not provide (found: {', '.join(sorted(discovered)) or 'none'})"
                )
                raise ValueError(msg)

    if include is not None:
        return [(name, path) for name, path in found if name in include]
    return [(name, path) for name, path in found if name not in (exclude or [])]


def _explicit_skills(
    source_root: Path, mapping: dict[str, str], label: str
) -> list[tuple[str, Path]]:
    resolved: list[tuple[str, Path]] = []
    for name, relative in mapping.items():
        skill_dir = _join_within(source_root, relative, label, f"skill {name!r} path")
        if _find_skill_md(skill_dir) is None:
            msg = f"{label}: skill {name!r} at {skill_dir} has no SKILL.md"
            raise ValueError(msg)
        resolved.append((name, skill_dir))
    return resolved


def _explicit_agents(
    source_root: Path, mapping: dict[str, str], label: str
) -> list[tuple[str, Path]]:
    resolved: list[tuple[str, Path]] = []
    for name, relative in mapping.items():
        agent_file = _join_within(source_root, relative, label, f"agent {name!r} path")
        if not agent_file.is_file() or agent_file.suffix != ".md":
            msg = f"{label}: agent {name!r} at {agent_file} is not a .md file"
            raise ValueError(msg)
        resolved.append((name, agent_file))
    return resolved


DISCOVERERS: dict[
    str, Callable[[Path, str, Mapping[str, Any], str], list[tuple[str, Path]]]
] = {"skills": _discover_skills, "agents": _discover_agents}

EXPLICIT_RESOLVERS: dict[
    str, Callable[[Path, dict[str, str], str], list[tuple[str, Path]]]
] = {"skills": _explicit_skills, "agents": _explicit_agents}


def agent_harness_build_plugin_resources(
    sources: list[SourceConfig], cache_dir: str
) -> dict[str, list[dict[str, Any]]]:
    """Resolve every plugin in the resolved sources to files on disk.

    Args:
        sources: Sources already resolved for this profile
        cache_dir: Path to the cache directory for git repos

    Returns:
        Dict with 'skills', 'agents' and 'hooks' keys for Ansible/Jinja2
    """
    resources = PluginResources()

    for source in sources:
        is_repo = "repo" in source
        if is_repo:
            origin = source["repo"]
            source_root = Path(cache_dir) / _repo_to_cache_name(origin)
        else:
            origin = "local"
            source_root = Path(source["local"])
        source_label = f"source {_source_label(source)}"

        for entry in source.get("plugins", []):
            plugin = ResolvedPlugin.from_dict(_as_plugin_mapping(entry, source_label))
            label = f"{source_label}: plugin {plugin.name}"

            # An explicit map decides the whole plugin: no manifest is consulted
            # for either kind, and the plugin contributes no hooks. Its root is
            # the source, which is all ${CLAUDE_PLUGIN_ROOT} has to point at.
            manifest: Mapping[str, Any] | None = None
            plugin_root = source_root
            if not plugin.explicit_mode:
                located = _find_manifest(source_root, is_repo, plugin.name, label)
                if located is None:
                    msg = (
                        f"{label}: no manifest found under {source_root} and no "
                        f"explicit skills/agents map to fall back on"
                    )
                    raise ValueError(msg)
                plugin_root, manifest = located

            for kind in RESOURCE_KINDS:
                explicit = plugin.explicit[kind]
                if manifest is None:
                    found = (
                        []
                        if explicit is None
                        else EXPLICIT_RESOLVERS[kind](source_root, explicit, label)
                    )
                else:
                    found = _apply_selection(
                        DISCOVERERS[kind](plugin_root, plugin.name, manifest, label),
                        plugin.include[kind],
                        plugin.exclude[kind],
                        label,
                        kind,
                    )

                resources.by_kind[kind].extend(
                    ResourceInfo(
                        name=name,
                        source=str(path),
                        origin=origin,
                        plugin_root=str(plugin_root),
                        target_agents=list(plugin.target_agents),
                        exclude_data=list(plugin.exclude_data),
                    )
                    for name, path in found
                )

            if manifest is None or not plugin.hooks:
                continue
            hooks = _read_plugin_hooks(plugin_root, manifest, label)
            if hooks is not None:
                hooks = hooks.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
                hooks = hooks.replace("$CLAUDE_PLUGIN_ROOT", str(plugin_root))
                resources.add_hooks(
                    HookFragment(
                        name=plugin.name,
                        content=hooks,
                        plugin_root=str(plugin_root),
                    )
                )

    return resources.to_dict()


def _read_plugin_hooks(
    plugin_path: Path, manifest: Mapping[str, Any], label: str
) -> str | None:
    """Read hook definitions from the manifest already resolved for this plugin.

    The manifest's "hooks" key takes precedence (mirrors Claude Code behavior).
    Falls back to hooks/hooks.json only when the manifest has no hooks field.
    """
    declared: Any = manifest.get("hooks")
    match declared:
        case dict():
            return json.dumps(cast(dict[str, Any], declared))
        case str():
            return _read_hooks_file(
                _join_within(plugin_path, declared, label, "hooks path")
            )
        case list():
            merged: dict[str, Any] = {}
            for path_ref in cast(list[Any], declared):
                if not isinstance(path_ref, str):
                    continue
                content = _read_hooks_file(
                    _join_within(plugin_path, path_ref, label, "hooks path")
                )
                if content:
                    try:
                        fragment: dict[str, Any] = json.loads(content)
                        merged.update(fragment)
                    except json.JSONDecodeError:
                        continue
            return json.dumps(merged) if merged else None
        case _:
            return _read_hooks_file(plugin_path / "hooks" / "hooks.json")


def _read_hooks_file(path: Path) -> str | None:
    """Read a hooks file, resolving relative paths."""
    resolved = path.resolve()
    if resolved.exists():
        try:
            return resolved.read_text()
        except OSError:
            pass
    return None


def agent_harness_repo_to_cache_name(repo: str) -> str:
    """Public filter: normalize a repo identifier to a filesystem-safe cache name."""
    return _repo_to_cache_name(repo)


def _transform_resource_name(name: str, name_transform: str) -> str:
    """Transform a resource name for a harness filesystem."""
    if name_transform == "preserve":
        return name
    if name_transform == "lowercase_dash":
        return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    msg = f"Unknown agent harness name transform: {name_transform}"
    raise ValueError(msg)


def agent_harness_filter_resources(
    resources: list[dict[str, Any]],
    target_agent: str,
    name_transform: str = "preserve",
    explicit_only: bool = False,
) -> list[dict[str, Any]]:
    """Select resources for an agent and transform their deployment names.

    An explicit-only agent receives just the resources that name it in
    target_agents; untargeted resources, which normally go everywhere, skip it.
    """
    filtered_resources: list[dict[str, Any]] = []
    resources_by_name: dict[str, dict[str, Any]] = {}
    for resource in resources:
        if not resource["target_agents"]:
            if explicit_only:
                continue
        elif target_agent not in resource["target_agents"]:
            continue
        transformed_resource = {
            **resource,
            "name": _transform_resource_name(resource["name"], name_transform),
        }
        name = transformed_resource["name"]
        if existing_resource := resources_by_name.get(name):
            msg = (
                f"Multiple resources target {target_agent}:{name}: "
                f"{existing_resource['source']} and {resource['source']}"
            )
            raise ValueError(msg)
        resources_by_name[name] = transformed_resource
        filtered_resources.append(transformed_resource)
    return filtered_resources


# =============================================================================
# Skill transformation (model alias replacement)
# =============================================================================


@dataclass
class SkillTransformResult:
    """Result of transforming a skill for a target agent."""

    content: str
    modified: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for Ansible/Jinja2 compatibility."""
        return {
            "content": self.content,
            "modified": self.modified,
        }


def _build_model_alias_map(
    models_config: dict[str, Any],
) -> dict[str, dict[str, str]]:
    """Build a lookup map from source aliases to target agent model names.

    Args:
        models_config: The 'models' section from models.yml

    Returns:
        Dict mapping source_alias -> {target_agent -> replacement_model}
        e.g., {"sonnet": {"opencode": "anthropic/claude-sonnet-4-5-..."}}
    """
    alias_map: dict[str, dict[str, str]] = {}

    for provider_models in models_config.values():
        if not isinstance(provider_models, dict):
            continue

        for model_config in cast(dict[str, Any], provider_models).values():
            if not isinstance(model_config, dict):
                continue

            harness_config = cast(dict[str, Any], model_config).get("agent_harness")
            if not harness_config or not isinstance(harness_config, dict):
                continue

            aliases = cast(dict[str, Any], harness_config).get("aliases")
            if not aliases or not isinstance(aliases, dict):
                continue

            aliases_dict = cast(dict[str, str], aliases)
            for source_alias in aliases_dict.values():
                if source_alias not in alias_map:
                    alias_map[source_alias] = {}

                for tgt_agent, tgt_alias in aliases_dict.items():
                    alias_map[source_alias][tgt_agent] = tgt_alias

    return alias_map


def _deep_convert_to_dict(obj: Any) -> Any:
    """Recursively convert Ansible lazy containers to regular Python types.

    Ansible passes _AnsibleLazyTemplateDict and similar types that can't be
    serialized by standard YAML libraries.
    """
    if isinstance(obj, dict):
        return {
            str(k): _deep_convert_to_dict(v)
            for k, v in cast(dict[Any, Any], obj).items()
        }
    if isinstance(obj, list):
        return [_deep_convert_to_dict(item) for item in cast(list[Any], obj)]
    return obj


def agent_harness_transform_skill_content(
    content: str,
    target_agent: str,
    models_config: dict[str, Any],
    plugin_root: str = "",
    name_override: str = "",
) -> dict[str, Any]:
    """Transform skill/agent Markdown content for the target agent.

    Applies up to three transformations:
    1. Model alias replacement in frontmatter (e.g., "sonnet" → provider-specific ID)
    2. ${CLAUDE_PLUGIN_ROOT} substitution with the absolute plugin path
    3. Frontmatter name rewrite (for agent namespace prefixing)
    """
    modified = False

    # Model alias replacement — regex on the model: line in frontmatter
    model_match = re.search(r"^model:\s*(.+)$", content, flags=re.MULTILINE)
    if model_match:
        model_value = model_match.group(1).strip()
        plain_config = _deep_convert_to_dict(models_config)
        alias_map = _build_model_alias_map(plain_config)
        replacement = alias_map.get(model_value, {}).get(target_agent)
        if replacement and replacement != model_value:
            content = re.sub(
                r"^(model:\s*).+$",
                rf"\g<1>{replacement}",
                content,
                count=1,
                flags=re.MULTILINE,
            )
            modified = True

    # Plugin root substitution (handle both ${VAR} and $VAR syntax)
    if plugin_root and "CLAUDE_PLUGIN_ROOT" in content:
        content = content.replace("${CLAUDE_PLUGIN_ROOT}", plugin_root)
        content = content.replace("$CLAUDE_PLUGIN_ROOT", plugin_root)
        modified = True

    # Frontmatter name rewrite — uses regex to avoid re-serializing the full
    # frontmatter block. Some agent descriptions contain colons and other YAML
    # metacharacters that cause the frontmatter library to choke on parsing.
    if name_override:
        transformed_content = re.sub(
            r"^(name:\s*).+$",
            rf"\g<1>{name_override}",
            content,
            count=1,
            flags=re.MULTILINE,
        )
        if transformed_content != content:
            content = transformed_content
            modified = True

    return SkillTransformResult(content=content, modified=modified).to_dict()


def agent_harness_transform_skill(
    source_path: str,
    target_agent: str,
    models_config: dict[str, Any],
    plugin_root: str = "",
    name_override: str = "",
) -> dict[str, Any]:
    """Transform a skill/agent .md file for the target agent.

    Args:
        source_path: Path to the source .md file (SKILL.md or agent .md)
        target_agent: Target agent name (e.g., "opencode", "claude", "amp")
        models_config: The 'models' section from models.yml
        plugin_root: Absolute path to substitute for ${CLAUDE_PLUGIN_ROOT}
        name_override: If set, rewrite the frontmatter name field to this value

    Returns:
        Dict with 'content' (transformed file content) and 'modified' (bool)
    """
    path = Path(source_path)
    if not path.exists():
        return SkillTransformResult(content="", modified=False).to_dict()

    return agent_harness_transform_skill_content(
        path.read_text(), target_agent, models_config, plugin_root, name_override
    )


class FilterModule:
    """Ansible filter plugin for agent harness."""

    def filters(self) -> dict[str, object]:
        return {
            "agent_harness_build_plugin_resources": agent_harness_build_plugin_resources,
            "agent_harness_resolve_sources": agent_harness_resolve_sources,
            "agent_harness_filter_resources": agent_harness_filter_resources,
            "agent_harness_transform_skill": agent_harness_transform_skill,
            "agent_harness_transform_skill_content": agent_harness_transform_skill_content,
            "agent_harness_repo_to_cache_name": agent_harness_repo_to_cache_name,
        }
