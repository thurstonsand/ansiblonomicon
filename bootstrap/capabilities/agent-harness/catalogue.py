"""Read and render the shared agent-harness catalogue without side effects."""

from collections.abc import Callable
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib
from typing import TypedDict, cast

import jinja2
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness_filters as filters
from harness_filters import SourceConfig

CAPABILITY = "bootstrap/capabilities/agent-harness"


class Profile(TypedDict):
    target_agents: list[str]
    explicit_only: list[str]


class Layout(TypedDict):
    skills_dir: str
    agents_dir: str | None
    name_transform: str


class FileMetadata(TypedDict):
    owner: str
    source: str | None
    mode: str


class NativeResource(TypedDict):
    owner: str
    destination: Path
    kind: str
    declaration: dict[str, object]
    variables: dict[str, object]


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("Expected a mapping")
    entries = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in entries):
        raise ValueError("Expected string mapping keys")
    return cast(dict[str, object], entries)


def strings(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Expected a list of strings")
    entries = cast(list[object], value)
    if not all(isinstance(entry, str) for entry in entries):
        raise ValueError("Expected a list of strings")
    return cast(list[str], entries)


def environment(repo: Path, home: Path, hostname: str) -> jinja2.Environment:
    env = jinja2.Environment(
        undefined=jinja2.StrictUndefined, keep_trailing_newline=True
    )

    def matches(value: str, pattern: str) -> bool:
        return re.match(pattern, value) is not None

    cast(dict[str, Callable[..., object]], env.tests)["match"] = matches

    def lookup(kind: str, path: str) -> str:
        if kind != "file":
            raise ValueError(f"Unsupported harness template lookup: {kind}")
        source = Path(path).resolve()
        if not source.is_relative_to(repo.resolve()):
            raise ValueError(f"Template lookup escapes checkout: {source}")
        return source.read_text().rstrip("\n")

    cast(dict[str, object], env.globals).update(
        home=str(home),
        hostname=hostname,
        agent_harness_root=str(repo / CAPABILITY),
        lookup=lookup,
    )
    return env


def load_profile(repo: Path, profile: str) -> Profile:
    profiles = mapping(
        mapping(tomllib.loads((repo / CAPABILITY / "profiles.toml").read_text()))[
            "profiles"
        ]
    )
    if profile not in profiles:
        raise ValueError(f"Unknown harness profile: {profile}")
    raw_profile = mapping(profiles[profile])
    return {
        "target_agents": strings(raw_profile["target_agents"]),
        "explicit_only": strings(raw_profile.get("explicit_only", [])),
    }


def declarations(
    repo: Path, home: Path, profile: str, hostname: str
) -> tuple[jinja2.Environment, Profile, dict[str, Layout], list[SourceConfig]]:
    env = environment(repo, home, hostname)
    canonical = repo / CAPABILITY / "catalogue.toml"
    profiles_path = repo / CAPABILITY / "profiles.toml"
    if not canonical.is_file() or not profiles_path.is_file():
        raise ValueError("Canonical harness catalogue and profiles are required")
    catalogue_data = mapping(tomllib.loads(canonical.read_text()))
    profile_data = mapping(tomllib.loads(profiles_path.read_text()))
    config = {
        "agent_harness_profiles": profile_data["profiles"],
        "agent_harness_sources": catalogue_data["sources"],
    }
    harness_root = repo / CAPABILITY / "harnesses"
    declarations = sorted(harness_root.glob("*/mise.toml"))
    if not declarations:
        raise ValueError("Canonical harness layouts are required")
    raw_layouts: dict[str, object] = {}
    for declaration in declarations:
        entry = mapping(tomllib.loads(declaration.read_text())["harness"])
        raw_layouts[str(entry["name"])] = {
            "skills_dir": str(entry["skills_root"]).replace("~", str(home), 1),
            "agents_dir": (
                str(entry["agents_root"]).replace("~", str(home), 1)
                if "agents_root" in entry
                else None
            ),
            "name_transform": entry["name_transform"],
        }
    layouts: dict[str, Layout] = {}
    for name, value in raw_layouts.items():
        entry = mapping(value)
        skills_dir = entry["skills_dir"]
        agents_dir = entry["agents_dir"]
        transform = entry["name_transform"]
        if (
            not isinstance(skills_dir, str)
            or not isinstance(transform, str)
            or not (agents_dir is None or isinstance(agents_dir, str))
        ):
            raise ValueError(f"Invalid harness layout: {name}")
        layouts[name] = {
            "skills_dir": skills_dir,
            "agents_dir": agents_dir,
            "name_transform": transform,
        }
    profiles = mapping(config["agent_harness_profiles"])
    selected_profile = load_profile(repo, profile)
    unknown = sorted(set(selected_profile["target_agents"]) - set(layouts))
    if unknown:
        raise ValueError(f"Unknown target harness(es): {', '.join(unknown)}")
    raw_sources = config["agent_harness_sources"]
    if not isinstance(raw_sources, list):
        raise ValueError("Expected harness source list")
    source_entries = [mapping(source) for source in cast(list[object], raw_sources)]
    local_catalogue = repo / CAPABILITY / "local" / hostname / "catalogue.toml"
    local_entries: list[dict[str, object]] = []
    if local_catalogue.is_file():
        local_data = mapping(tomllib.loads(local_catalogue.read_text()))
        if set(local_data) - {"sources"} or not isinstance(
            local_data.get("sources", []), list
        ):
            raise ValueError(f"{local_catalogue}: only a sources array is supported")
        local_entries = [
            mapping(source)
            for source in cast(list[object], local_data.get("sources", []))
        ]
    for source in [*source_entries, *local_entries]:
        local = source.get("local")
        if isinstance(local, str) and not Path(local).is_absolute():
            source["local"] = str(repo / local)
    sources = filters.agent_harness_resolve_sources(
        source_entries,
        profile,
        list(profiles),
        list(layouts),
        local_entries,
    )
    return env, selected_profile, layouts, sources


def load_models(repo: Path) -> dict[str, object]:
    document = mapping(yaml.safe_load((repo / CAPABILITY / "models.yml").read_text()))
    return mapping(document["models"])


def excluded(path: Path, patterns: list[str]) -> bool:
    return any(part in {".git", ".claude-plugin"} for part in path.parts) or any(
        fnmatch.fnmatch(path.as_posix(), pattern.lstrip("/"))
        or any(fnmatch.fnmatch(part, pattern) for part in path.parts)
        for pattern in patterns
    )


def selection_fingerprints(sources: list[SourceConfig]) -> dict[str, str]:
    """Fingerprint profile-resolved selectors, grouped by stable plugin owner."""
    rows: dict[str, list[str]] = {}
    fields = (
        "skills",
        "agents",
        "include_skills",
        "exclude_skills",
        "include_agents",
        "exclude_agents",
    )
    for source in sources:
        source_id = str(source.get("repo") or source.get("local"))
        for plugin in source.get("plugins", []):
            if plugin.get("remove", False):
                continue
            owner = f"{source_id}\0{plugin['name']}"
            declaration = {field: plugin.get(field) for field in fields}
            rows.setdefault(owner, []).append(
                json.dumps(declaration, sort_keys=True, separators=(",", ":"))
            )
    return {
        owner: hashlib.sha256(
            json.dumps(sorted(entries), separators=(",", ":")).encode()
        ).hexdigest()
        for owner, entries in rows.items()
    }


def render_files(
    repo: Path,
    home: Path,
    cache: Path,
    profile: str,
    hostname: str,
    *,
    trim_blocks: bool,
    metadata: dict[Path, FileMetadata] | None = None,
    sources_override: list[SourceConfig] | None = None,
    allow_missing_selections: set[str] | None = None,
) -> dict[Path, tuple[bytes, int]]:
    env, selected_profile, layouts, sources = declarations(
        repo, home, profile, hostname
    )
    env.trim_blocks = trim_blocks
    if sources_override is not None:
        sources = sources_override
    resources = filters.agent_harness_build_plugin_resources(
        sources, str(cache), allow_missing_selections
    )
    models = load_models(repo)
    files: dict[Path, tuple[bytes, int]] = {}

    def add(
        path: Path,
        content: bytes,
        mode: int,
        owner: str,
        source: Path | None = None,
        deploy_mode: str = "copy",
    ) -> None:
        detail: FileMetadata = {
            "owner": owner,
            "source": str(source) if source is not None else None,
            "mode": deploy_mode,
        }
        if path in files:
            same_metadata = metadata is None or metadata[path] == detail
            if files[path] == (content, mode) and same_metadata:
                return
            raise ValueError(f"Conflicting harness destination: {path}")
        if not path.is_relative_to(home) or path == home:
            raise ValueError(f"Harness destination escapes operator home: {path}")
        files[path] = (content, mode)
        if metadata is not None:
            metadata[path] = detail

    for target in selected_profile["target_agents"]:
        layout = layouts[target]
        for kind in ("skills", "agents"):
            destination = (
                layout["skills_dir"] if kind == "skills" else layout["agents_dir"]
            )
            if destination is None:
                continue
            selected = filters.agent_harness_filter_resources(
                resources[kind],
                target,
                layout["name_transform"],
                target in selected_profile.get("explicit_only", []),
            )
            for resource in selected:
                source = Path(resource["source"])
                owner = f"{resource['source_id']}\0{resource['plugin_name']}"
                name = resource["name"]
                if Path(name).name != name or name in {".", ".."}:
                    raise ValueError(f"Invalid harness resource name: {name}")
                if kind == "agents":
                    transformed = filters.agent_harness_transform_skill(
                        str(source), target, models, resource["plugin_root"], name
                    )
                    agent_content = transformed["content"]
                    local_link = (
                        resource["origin"] == "local" and not transformed["modified"]
                    )
                    mode = source.stat().st_mode & 0o777 if local_link else 0o644
                    add(
                        Path(destination) / f"{name}.md",
                        agent_content.encode(),
                        mode,
                        owner,
                        source if local_link else None,
                        "symlink" if local_link else "copy",
                    )
                    continue
                for asset in sorted(source.rglob("*")):
                    relative = asset.relative_to(source)
                    if (
                        excluded(relative, resource["exclude_data"])
                        or not asset.is_file()
                    ):
                        continue
                    if not asset.resolve().is_relative_to(source.resolve()):
                        raise ValueError(f"Skill asset escapes source: {asset}")
                    output = (
                        relative.with_suffix("") if asset.suffix == ".j2" else relative
                    )
                    if (
                        asset.name == "SKILL.md"
                        and asset.with_suffix(".md.j2").exists()
                    ):
                        continue
                    content = asset.read_bytes()
                    transformed_asset = False
                    if asset.suffix == ".j2":
                        content = env.from_string(content.decode()).render().encode()
                        transformed_asset = True
                    if output.name == "SKILL.md":
                        transformed = filters.agent_harness_transform_skill_content(
                            content.decode(),
                            target,
                            models,
                            resource["plugin_root"],
                            name,
                        )
                        content = transformed["content"].encode()
                        transformed_asset |= transformed["modified"]
                    local_link = resource["origin"] == "local" and not transformed_asset
                    mode = (
                        asset.stat().st_mode & 0o777
                        if local_link
                        else (0o755 if asset.stat().st_mode & 0o111 else 0o644)
                    )
                    add(
                        Path(destination) / name / output,
                        content,
                        mode,
                        owner,
                        asset if local_link else None,
                        "symlink" if local_link else "copy",
                    )
    for hook in resources["hooks"]:
        if Path(hook["name"]).name != hook["name"]:
            raise ValueError(f"Invalid hook name: {hook['name']}")
        add(
            cache / "hooks" / f"{hook['name']}.json",
            hook["content"].encode(),
            0o644,
            f"{hook['source_id']}\0{hook['plugin_name']}",
        )
    return files


def native_resources(
    repo: Path, home: Path, enabled_harnesses: list[str]
) -> list[NativeResource]:
    """Load declarations for mise to interpret, only rebasing their sources."""
    resources: list[NativeResource] = []
    root = repo / CAPABILITY / "harnesses"
    for target in enabled_harnesses:
        declaration = root / target / "mise.toml"
        document = mapping(tomllib.loads(declaration.read_text()))
        variables = mapping(document.get("vars", {}))
        bootstrap = mapping(document.get("bootstrap", {}))
        groups = {
            "dotfiles": mapping(document.get("dotfiles", {})),
            "files": mapping(bootstrap.get("files", {})),
        }
        for kind, entries in groups.items():
            for raw_destination, raw_value in entries.items():
                value = mapping(raw_value)
                source = value.get("source")
                if isinstance(source, str):
                    source_path = Path(source).expanduser()
                    if not source_path.is_absolute():
                        source_path = declaration.parent / source_path
                    source_path = source_path.resolve()
                    if not source_path.is_relative_to(declaration.parent.resolve()):
                        raise ValueError(
                            f"Native harness source escapes declaration: {source_path}"
                        )
                    value["source"] = str(source_path)
                destination = Path(raw_destination.replace("~", str(home), 1))
                if not destination.is_absolute():
                    destination = home / destination
                resources.append(
                    {
                        "owner": f"native:{target}",
                        "destination": destination,
                        "kind": kind,
                        "declaration": value,
                        "variables": variables,
                    }
                )
    return resources
