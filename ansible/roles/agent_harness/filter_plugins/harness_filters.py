"""Filter plugins for agent_harness role."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, TypedDict, cast

import frontmatter


class PluginLongForm(TypedDict, total=False):
    """Long form plugin config with optional exclusions and agent targeting."""

    name: str
    path: str
    skills: str | list[str]  # override skills search paths within plugin
    agents: str | list[str]  # override agents search paths within plugin
    exclude_skills: list[str]
    exclude_agents: list[str]
    exclude_data: list[str]  # rsync --exclude patterns for deployed files
    target_agents: list[str]


@dataclass
class ResourceInfo:
    """Info about a discovered resource (skill or agent)."""

    name: str
    source: str
    origin: str
    target_agents: list[str] = field(default_factory=list)
    exclude_data: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for Ansible/Jinja2 compatibility."""
        return {
            "name": self.name,
            "source": self.source,
            "origin": self.origin,
            "target_agents": list(self.target_agents),
            "exclude_data": list(self.exclude_data),
        }


@dataclass
class PluginResources:
    """All resources discovered from plugin sources."""

    skills: list[ResourceInfo] = field(default_factory=list)
    agents: list[ResourceInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        """Convert to dict for Ansible/Jinja2 compatibility."""
        return {
            "skills": [s.to_dict() for s in self.skills],
            "agents": [a.to_dict() for a in self.agents],
        }


@dataclass
class PluginConfig:
    """Unified plugin configuration from marketplace entry or plugin.json."""

    name: str
    source_path: str  # path to plugin directory (relative to repo root or absolute)
    skills_paths: list[str]  # paths to look for skills (relative to plugin root)
    agents_paths: list[str]  # paths to look for agents (relative to plugin root)


@dataclass
class ResolvedPlugin:
    """Result of resolving a plugin specification."""

    config: PluginConfig | None
    plugin_path: Path | None
    exclude_skills: list[str] = field(default_factory=list)
    exclude_agents: list[str] = field(default_factory=list)
    exclude_data: list[str] = field(default_factory=list)
    target_agents: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if plugin was successfully resolved."""
        return self.config is not None and self.plugin_path is not None

    @classmethod
    def empty(cls) -> "ResolvedPlugin":
        """Create an empty/invalid result."""
        return cls(config=None, plugin_path=None)


@dataclass
class GitSourceConfig:
    """Configuration for a git-based source."""

    repo: str
    pull: bool = True
    plugins: list[str | PluginLongForm] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GitSourceConfig":
        """Create from a raw dict (e.g., from Ansible YAML)."""
        return cls(
            repo=d["repo"],
            pull=d.get("pull", True),
            plugins=list(d.get("plugins", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to plain dict for Ansible (which can't serialize dataclasses)."""
        return {
            "repo": self.repo,
            "pull": self.pull,
            "plugins": list(self.plugins),
        }


SourceConfig = dict[str, Any]  # Union of git/local source dicts from Ansible


def _get_skills_paths(config: Mapping[str, str | list[str] | None]) -> list[str]:
    """Extract skills paths from a plugin config dict.

    Args:
        config: Plugin config dict (from marketplace entry or plugin.json)

    Returns:
        List of normalized skill paths, defaults to ["skills"]
    """
    skills_field: str | list[str] | None = config.get("skills")
    if skills_field is None:
        return ["skills"]

    if isinstance(skills_field, str):
        return [skills_field.lstrip("./")]

    # Must be list[str]
    return [p.lstrip("./") for p in skills_field]


def _get_agents_paths(config: Mapping[str, str | list[str] | None]) -> list[str]:
    """Extract agents paths from a plugin config dict.

    Args:
        config: Plugin config dict (from marketplace entry or plugin.json)

    Returns:
        List of normalized agent paths, defaults to ["agents"]
    """
    agents_field: str | list[str] | None = config.get("agents")
    if agents_field is None:
        return ["agents"]

    if isinstance(agents_field, str):
        return [agents_field.lstrip("./")]

    return [p.lstrip("./") for p in agents_field]


def _normalize_path_field(value: str | list[str]) -> list[str]:
    """Normalize a string or list of strings into a list of cleaned paths."""
    if isinstance(value, str):
        return [value.lstrip("./")]
    return [p.lstrip("./") for p in value]


def _load_plugin_json(plugin_path: Path) -> dict[str, str | list[str] | None] | None:
    """Load and parse plugin.json from a plugin directory.

    Args:
        plugin_path: Path to the plugin directory

    Returns:
        Parsed plugin config dict, or None if not found/invalid
    """
    plugin_json_path = plugin_path / ".claude-plugin" / "plugin.json"
    if not plugin_json_path.exists():
        return None

    try:
        with plugin_json_path.open() as f:
            return json.load(f)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError):
        return None


def _find_plugin_in_marketplace(
    repo_path: Path, plugin_name: str
) -> PluginConfig | None:
    """Look up a plugin by name in marketplace.json.

    Handles the `strict` field:
    - strict: true (default): load plugin.json from plugin directory
    - strict: false: use marketplace entry as the plugin config

    Args:
        repo_path: Path to the cloned repository
        plugin_name: Name of the plugin to find

    Returns:
        PluginConfig if found, None otherwise
    """
    marketplace_path = repo_path / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.exists():
        return None

    try:
        with marketplace_path.open() as f:
            marketplace = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    plugins = marketplace.get("plugins", [])
    plugin_root = marketplace.get("metadata", {}).get("pluginRoot", "")

    for plugin_entry in plugins:
        if plugin_entry.get("name") != plugin_name:
            continue

        # Found the plugin - resolve its source path
        source = plugin_entry.get("source", "")

        # Handle different source formats
        if isinstance(source, dict):
            # External source (github, url) - not supported for now
            continue
        elif isinstance(source, str):
            # Relative path
            if plugin_root and not source.startswith(("./", "/")):
                source = f"{plugin_root}/{source}"
            source = source.lstrip("./")
        else:
            continue

        plugin_path = repo_path / source

        # Check strict mode
        strict = plugin_entry.get("strict", True)

        if strict:
            # Load plugin.json and merge with marketplace entry
            plugin_json = _load_plugin_json(plugin_path)
            if plugin_json:
                # Marketplace entry overrides plugin.json for specified fields
                merged_config = {**plugin_json, **plugin_entry}
                skills_paths = _get_skills_paths(merged_config)
                agents_paths = _get_agents_paths(merged_config)
            else:
                # No plugin.json but strict=true, use marketplace entry
                skills_paths = _get_skills_paths(plugin_entry)
                agents_paths = _get_agents_paths(plugin_entry)
        else:
            # strict=false: marketplace entry IS the config
            skills_paths = _get_skills_paths(plugin_entry)
            agents_paths = _get_agents_paths(plugin_entry)

        return PluginConfig(
            name=plugin_name,
            source_path=source,
            skills_paths=skills_paths,
            agents_paths=agents_paths,
        )

    return None


def _check_standalone_plugin(repo_path: Path, plugin_name: str) -> PluginConfig | None:
    """Check if the repo is a standalone plugin (not a marketplace).

    A standalone plugin has .claude-plugin/plugin.json at the repo root.

    Args:
        repo_path: Path to the cloned repository
        plugin_name: Name of the plugin to find

    Returns:
        PluginConfig if this is a standalone plugin matching the name, None otherwise
    """
    plugin_json = _load_plugin_json(repo_path)
    if plugin_json is None:
        return None

    # Check if the plugin name matches
    if plugin_json.get("name") != plugin_name:
        return None

    return PluginConfig(
        name=plugin_name,
        source_path=".",
        skills_paths=_get_skills_paths(plugin_json),
        agents_paths=_get_agents_paths(plugin_json),
    )


def _find_skill_md(directory: Path) -> Path | None:
    """Find SKILL.md in a directory, case-insensitive.

    Returns the path to the skill file if found, or None if not found.
    """
    if not directory.exists():
        return None
    for entry in directory.iterdir():
        if entry.is_file() and entry.name.lower() == "skill.md":
            return entry
    return None


def _discover_skills_in_plugin(
    plugin_path: Path, skills_paths: list[str], root_skill_name: str
) -> list[str]:
    """Discover all skills within a plugin directory.

    Looks for directories containing SKILL.md files (case-insensitive).

    Args:
        plugin_path: Path to the plugin directory
        skills_paths: List of paths to search for skills (relative to plugin root)
        root_skill_name: Name to use if the plugin root itself is a skill

    Returns:
        List of skill names found
    """
    skills: list[str] = []

    # Check if plugin root has SKILL.md (plugin is the skill)
    if _find_skill_md(plugin_path):
        skills.append(root_skill_name)

    # Search each skills path
    for skills_base in skills_paths:
        skills_dir = plugin_path / skills_base
        if not skills_dir.exists() or not skills_dir.is_dir():
            continue

        # Find all subdirectories with SKILL.md
        for entry in skills_dir.iterdir():
            if entry.is_dir() and _find_skill_md(entry):
                skills.append(entry.name)

    return skills


def _get_skill_source_path(
    plugin_path: Path, skill_name: str, skills_paths: list[str], root_skill_name: str
) -> str | None:
    """Get the full path to a skill within a plugin.

    Args:
        plugin_path: Path to the plugin directory
        skill_name: Name of the skill
        skills_paths: List of paths to search for skills
        root_skill_name: Name used for root-level skill (for matching)

    Returns:
        Full path to skill directory, or None if not found
    """
    # Check if plugin root is the skill
    if _find_skill_md(plugin_path) and skill_name == root_skill_name:
        return str(plugin_path)

    # Search skills paths
    for skills_base in skills_paths:
        skill_dir = plugin_path / skills_base / skill_name
        if skill_dir.exists() and _find_skill_md(skill_dir):
            return str(skill_dir)

    return None


def _discover_agents_in_plugin(plugin_path: Path, agents_paths: list[str]) -> list[str]:
    """Discover all agents within a plugin directory.

    Looks for .md files in agent directories.

    Args:
        plugin_path: Path to the plugin directory
        agents_paths: List of paths to search for agents (relative to plugin root)

    Returns:
        List of agent names found (without .md extension)
    """
    agents: list[str] = []

    for agent_base in agents_paths:
        agent_dir = plugin_path / agent_base
        if not agent_dir.exists() or not agent_dir.is_dir():
            continue

        for entry in agent_dir.iterdir():
            if entry.is_file() and entry.suffix == ".md":
                agents.append(entry.stem)

    return agents


def _get_agent_source_path(
    plugin_path: Path, agent_name: str, agents_paths: list[str]
) -> str | None:
    """Get the full path to an agent within a plugin.

    Args:
        plugin_path: Path to the plugin directory
        agent_name: Name of the agent (without .md extension)
        agents_paths: List of paths to search for agents

    Returns:
        Full path to agent file, or None if not found
    """
    for agent_base in agents_paths:
        agent_file = plugin_path / agent_base / f"{agent_name}.md"
        if agent_file.exists():
            return str(agent_file)

    return None


def _resolve_plugin_from_repo(
    repo_path: Path, plugin_spec: str | PluginLongForm
) -> ResolvedPlugin:
    """Resolve a plugin specification from a git repo.

    Args:
        repo_path: Path to the cloned repository
        plugin_spec: Plugin name (str) or PluginLongForm dict

    Returns:
        ResolvedPlugin with config and paths, or empty if not resolvable
    """
    exclude_skills: list[str] = []
    exclude_agents: list[str] = []
    exclude_data: list[str] = []
    target_agents: list[str] = []

    skills_override: str | list[str] | None = None
    agents_override: str | list[str] | None = None

    if isinstance(plugin_spec, str):
        plugin_name = plugin_spec
        explicit_path = None
    else:
        plugin_name = plugin_spec.get("name", "")
        explicit_path = plugin_spec.get("path")
        skills_override = plugin_spec.get("skills")
        agents_override = plugin_spec.get("agents")
        exclude_skills = list(plugin_spec.get("exclude_skills", []))
        exclude_agents = list(plugin_spec.get("exclude_agents", []))
        exclude_data = list(plugin_spec.get("exclude_data", []))
        target_agents = list(plugin_spec.get("target_agents", []))

    def _apply_overrides(config: PluginConfig) -> PluginConfig:
        """Apply skills/agents path overrides from the plugin spec."""
        if skills_override is not None:
            config.skills_paths = _normalize_path_field(skills_override)
        if agents_override is not None:
            config.agents_paths = _normalize_path_field(agents_override)
        return config

    # If explicit path, use it directly
    if explicit_path:
        plugin_path = repo_path / explicit_path.removeprefix("./")
        plugin_json = _load_plugin_json(plugin_path)

        # Infer name from path if not provided
        if not plugin_name:
            plugin_name = plugin_path.name

        # When path is explicit with no plugin.json, scan the directory
        # itself rather than looking for a skills/ subdirectory
        no_config_default = {
            "skills": ["."],
            "agents": ["."],
        }
        config = _apply_overrides(
            PluginConfig(
                name=plugin_name,
                source_path=explicit_path,
                skills_paths=_get_skills_paths(plugin_json or no_config_default),
                agents_paths=_get_agents_paths(plugin_json or no_config_default),
            )
        )
        return ResolvedPlugin(
            config=config,
            plugin_path=plugin_path,
            exclude_skills=exclude_skills,
            exclude_agents=exclude_agents,
            exclude_data=exclude_data,
            target_agents=target_agents,
        )

    # Try marketplace lookup
    config = _find_plugin_in_marketplace(repo_path, plugin_name)
    if config:
        _apply_overrides(config)
        plugin_path = repo_path / config.source_path
        return ResolvedPlugin(
            config=config,
            plugin_path=plugin_path,
            exclude_skills=exclude_skills,
            exclude_agents=exclude_agents,
            exclude_data=exclude_data,
            target_agents=target_agents,
        )

    # Try standalone plugin
    config = _check_standalone_plugin(repo_path, plugin_name)
    if config:
        _apply_overrides(config)
        return ResolvedPlugin(
            config=config,
            plugin_path=repo_path,
            exclude_skills=exclude_skills,
            exclude_agents=exclude_agents,
            exclude_data=exclude_data,
            target_agents=target_agents,
        )

    return ResolvedPlugin.empty()


def _resolve_plugin_from_local(
    local_path: str, plugin_spec: str | PluginLongForm
) -> ResolvedPlugin:
    """Resolve a plugin specification from a local path.

    Args:
        local_path: Base path to local plugins
        plugin_spec: Plugin name (str) or PluginLongForm dict

    Returns:
        ResolvedPlugin with config and paths
    """
    exclude_skills: list[str] = []
    exclude_agents: list[str] = []
    exclude_data: list[str] = []
    target_agents: list[str] = []
    skills_override: str | list[str] | None = None
    agents_override: str | list[str] | None = None
    base_path = Path(local_path)

    if isinstance(plugin_spec, str):
        plugin_name = plugin_spec
        explicit_path = None
    else:
        plugin_name = plugin_spec.get("name", "")
        explicit_path = plugin_spec.get("path")
        skills_override = plugin_spec.get("skills")
        agents_override = plugin_spec.get("agents")
        exclude_skills = list(plugin_spec.get("exclude_skills", []))
        exclude_agents = list(plugin_spec.get("exclude_agents", []))
        exclude_data = list(plugin_spec.get("exclude_data", []))
        target_agents = list(plugin_spec.get("target_agents", []))

    # Determine plugin path
    if explicit_path:
        plugin_path = base_path / explicit_path.removeprefix("./")
        if not plugin_name:
            plugin_name = plugin_path.name
    else:
        # Try plugins/{name} structure first
        plugin_path = base_path / "plugins" / plugin_name
        # Then try {name} directly under base_path
        if not plugin_path.exists():
            plugin_path = base_path / plugin_name
        # Finally fall back to base_path itself (standalone plugin)
        if not plugin_path.exists():
            plugin_path = base_path

    plugin_json = _load_plugin_json(plugin_path)

    no_config_default = {"skills": ["."], "agents": ["."]} if explicit_path else {}
    config = PluginConfig(
        name=plugin_name,
        source_path=str(plugin_path),
        skills_paths=_get_skills_paths(plugin_json or no_config_default),
        agents_paths=_get_agents_paths(plugin_json or no_config_default),
    )

    if skills_override is not None:
        config.skills_paths = _normalize_path_field(skills_override)
    if agents_override is not None:
        config.agents_paths = _normalize_path_field(agents_override)

    return ResolvedPlugin(
        config=config,
        plugin_path=plugin_path,
        exclude_skills=exclude_skills,
        exclude_agents=exclude_agents,
        exclude_data=exclude_data,
        target_agents=target_agents,
    )


def agent_harness_build_plugin_resources(
    sources: list[SourceConfig], cache_dir: str
) -> dict[str, list[dict[str, Any]]]:
    """Build lists of skills and agents from plugin-based sources config.

    Args:
        sources: List of source configs (git repos or local paths)
        cache_dir: Path to the cache directory for git repos

    Returns:
        Dict with 'skills' and 'agents' keys for Ansible/Jinja2
    """
    skills: list[ResourceInfo] = []
    agents: list[ResourceInfo] = []

    for source in sources:
        if "repo" in source:
            # Git source
            repo = source["repo"]
            repo_cache_name = repo.replace("/", "--")
            repo_path = Path(cache_dir) / repo_cache_name
            plugins = source.get("plugins", [])

            for plugin_spec in plugins:
                resolved = _resolve_plugin_from_repo(repo_path, plugin_spec)
                if not resolved.is_valid:
                    continue

                config = resolved.config
                plugin_path = resolved.plugin_path
                assert config is not None
                assert plugin_path is not None

                # For root-level skills, use plugin name (or repo name as fallback)
                root_skill_name = config.name or repo.split("/")[-1]

                # Discover and add skills
                discovered_skills = _discover_skills_in_plugin(
                    plugin_path, config.skills_paths, root_skill_name
                )
                for skill_name in discovered_skills:
                    if skill_name in resolved.exclude_skills:
                        continue
                    source_path = _get_skill_source_path(
                        plugin_path, skill_name, config.skills_paths, root_skill_name
                    )
                    if source_path:
                        skills.append(
                            ResourceInfo(
                                name=skill_name,
                                source=source_path,
                                origin=repo,
                                target_agents=resolved.target_agents,
                                exclude_data=resolved.exclude_data,
                            )
                        )

                # Discover and add agents
                discovered_agents = _discover_agents_in_plugin(
                    plugin_path, config.agents_paths
                )
                for agent_name in discovered_agents:
                    if agent_name in resolved.exclude_agents:
                        continue
                    source_path = _get_agent_source_path(
                        plugin_path, agent_name, config.agents_paths
                    )
                    if source_path:
                        agents.append(
                            ResourceInfo(
                                name=agent_name,
                                source=source_path,
                                origin=repo,
                                target_agents=resolved.target_agents,
                                exclude_data=resolved.exclude_data,
                            )
                        )

        elif "local" in source:
            # Local source
            local_path = source["local"]
            plugins = source.get("plugins", [])

            for plugin_spec in plugins:
                resolved = _resolve_plugin_from_local(local_path, plugin_spec)
                if not resolved.is_valid:
                    continue

                config = resolved.config
                plugin_path = resolved.plugin_path
                assert config is not None
                assert plugin_path is not None

                # Discover and add skills
                discovered_skills = _discover_skills_in_plugin(
                    plugin_path, config.skills_paths, config.name
                )
                for skill_name in discovered_skills:
                    if skill_name in resolved.exclude_skills:
                        continue
                    source_path = _get_skill_source_path(
                        plugin_path, skill_name, config.skills_paths, config.name
                    )
                    if source_path:
                        skills.append(
                            ResourceInfo(
                                name=skill_name,
                                source=source_path,
                                origin="local",
                                target_agents=resolved.target_agents,
                                exclude_data=resolved.exclude_data,
                            )
                        )

                # Discover and add agents
                discovered_agents = _discover_agents_in_plugin(
                    plugin_path, config.agents_paths
                )
                for agent_name in discovered_agents:
                    if agent_name in resolved.exclude_agents:
                        continue
                    source_path = _get_agent_source_path(
                        plugin_path, agent_name, config.agents_paths
                    )
                    if source_path:
                        agents.append(
                            ResourceInfo(
                                name=agent_name,
                                source=source_path,
                                origin="local",
                                target_agents=resolved.target_agents,
                                exclude_data=resolved.exclude_data,
                            )
                        )

    return PluginResources(skills=skills, agents=agents).to_dict()


def agent_harness_get_git_sources(sources: list[SourceConfig]) -> list[dict[str, Any]]:
    """Extract only git sources from the sources list.

    Args:
        sources: List of source configs

    Returns:
        List of git source configs as dicts (Ansible can't serialize dataclasses)
    """
    return [GitSourceConfig.from_dict(s).to_dict() for s in sources if "repo" in s]


def agent_harness_filter_resources(
    resources: list[dict[str, Any]], target_agent: str
) -> list[dict[str, Any]]:
    """Filter resources to those that should deploy to a specific agent.

    A resource is included if:
    - target_agents is empty (deploy to all agents), OR
    - target_agents contains the target_agent

    Args:
        resources: List of resource dicts (from PluginResources.to_dict())
        target_agent: Name of the agent to filter for

    Returns:
        Filtered list of resources for the target agent
    """
    return [
        r
        for r in resources
        if not r["target_agents"] or target_agent in r["target_agents"]
    ]


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


def _serialize_frontmatter(metadata: dict[str, Any], content: str) -> str:
    """Serialize frontmatter manually to avoid Ansible's YAML representer pollution.

    Ansible modifies PyYAML's global representers which can cause issues with
    frontmatter.dumps(). This function builds the output manually.
    """
    import yaml

    yaml_content = yaml.dump(
        dict(metadata),
        Dumper=yaml.SafeDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=True,
    )
    return f"---\n{yaml_content}---\n\n{content}"


def agent_harness_transform_skill(
    source_path: str, target_agent: str, models_config: dict[str, Any]
) -> dict[str, Any]:
    """Transform a skill's frontmatter model field for the target agent.

    Skills may specify a model alias (e.g., "sonnet") in their frontmatter.
    Different agents use different model naming conventions:
    - Claude/Amp: "sonnet", "haiku", "opus"
    - OpenCode: "anthropic/claude-sonnet-4-5-20250929"

    This function rewrites the model field based on the target agent.

    Args:
        source_path: Path to the source skill file (SKILL.md)
        target_agent: Target agent name (e.g., "opencode", "claude", "amp")
        models_config: The 'models' section from models.yml

    Returns:
        Dict with 'content' (transformed file content) and 'modified' (bool)
    """
    path = Path(source_path)
    if not path.exists():
        return SkillTransformResult(content="", modified=False).to_dict()

    content = path.read_text()
    post = frontmatter.loads(content)

    model_value = post.metadata.get("model")
    if not model_value or not isinstance(model_value, str):
        return SkillTransformResult(content=content, modified=False).to_dict()

    plain_config = _deep_convert_to_dict(models_config)
    alias_map = _build_model_alias_map(plain_config)

    replacement = alias_map.get(model_value, {}).get(target_agent)
    if not replacement or replacement == model_value:
        return SkillTransformResult(content=content, modified=False).to_dict()

    new_metadata = _deep_convert_to_dict(dict(post.metadata))
    new_metadata["model"] = str(replacement)
    serialized = _serialize_frontmatter(new_metadata, post.content)
    return SkillTransformResult(content=serialized, modified=True).to_dict()


class FilterModule:
    """Ansible filter plugin for agent harness."""

    def filters(self) -> dict[str, object]:
        return {
            "agent_harness_build_plugin_resources": agent_harness_build_plugin_resources,
            "agent_harness_get_git_sources": agent_harness_get_git_sources,
            "agent_harness_filter_resources": agent_harness_filter_resources,
            "agent_harness_transform_skill": agent_harness_transform_skill,
        }
