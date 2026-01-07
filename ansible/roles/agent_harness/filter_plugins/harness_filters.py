"""Filter plugins for agent_harness role."""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, TypedDict


class PluginLongForm(TypedDict, total=False):
    """Long form plugin config with optional exclusions and agent targeting."""

    name: str
    path: str
    exclude_skills: list[str]
    exclude_commands: list[str]
    exclude_agents: list[str]
    target_agents: list[str]


@dataclass
class ResourceInfo:
    """Info about a discovered resource (skill, command, or agent)."""

    name: str
    source: str
    origin: str
    target_agents: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for Ansible/Jinja2 compatibility."""
        return {
            "name": self.name,
            "source": self.source,
            "origin": self.origin,
            "target_agents": list(self.target_agents),
        }


@dataclass
class PluginResources:
    """All resources discovered from plugin sources."""

    skills: list[ResourceInfo] = field(default_factory=list)
    commands: list[ResourceInfo] = field(default_factory=list)
    agents: list[ResourceInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        """Convert to dict for Ansible/Jinja2 compatibility."""
        return {
            "skills": [s.to_dict() for s in self.skills],
            "commands": [c.to_dict() for c in self.commands],
            "agents": [a.to_dict() for a in self.agents],
        }


@dataclass
class PluginConfig:
    """Unified plugin configuration from marketplace entry or plugin.json."""

    name: str
    source_path: str  # path to plugin directory (relative to repo root or absolute)
    skills_paths: list[str]  # paths to look for skills (relative to plugin root)
    commands_paths: list[str]  # paths to look for commands (relative to plugin root)
    agents_paths: list[str]  # paths to look for agents (relative to plugin root)


@dataclass
class ResolvedPlugin:
    """Result of resolving a plugin specification."""

    config: PluginConfig | None
    plugin_path: Path | None
    exclude_skills: list[str] = field(default_factory=list)
    exclude_commands: list[str] = field(default_factory=list)
    exclude_agents: list[str] = field(default_factory=list)
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


def _get_skills_paths(config: dict[str, str | list[str] | None]) -> list[str]:
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


def _get_commands_paths(config: dict[str, str | list[str] | None]) -> list[str]:
    """Extract commands paths from a plugin config dict.

    Args:
        config: Plugin config dict (from marketplace entry or plugin.json)

    Returns:
        List of normalized command paths, defaults to ["commands"]
    """
    commands_field: str | list[str] | None = config.get("commands")
    if commands_field is None:
        return ["commands"]

    if isinstance(commands_field, str):
        return [commands_field.lstrip("./")]

    return [p.lstrip("./") for p in commands_field]


def _get_agents_paths(config: dict[str, str | list[str] | None]) -> list[str]:
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
                commands_paths = _get_commands_paths(merged_config)
                agents_paths = _get_agents_paths(merged_config)
            else:
                # No plugin.json but strict=true, use marketplace entry
                skills_paths = _get_skills_paths(plugin_entry)
                commands_paths = _get_commands_paths(plugin_entry)
                agents_paths = _get_agents_paths(plugin_entry)
        else:
            # strict=false: marketplace entry IS the config
            skills_paths = _get_skills_paths(plugin_entry)
            commands_paths = _get_commands_paths(plugin_entry)
            agents_paths = _get_agents_paths(plugin_entry)

        return PluginConfig(
            name=plugin_name,
            source_path=source,
            skills_paths=skills_paths,
            commands_paths=commands_paths,
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
        commands_paths=_get_commands_paths(plugin_json),
        agents_paths=_get_agents_paths(plugin_json),
    )


def _discover_skills_in_plugin(
    plugin_path: Path, skills_paths: list[str], root_skill_name: str
) -> list[str]:
    """Discover all skills within a plugin directory.

    Looks for directories containing SKILL.md files.

    Args:
        plugin_path: Path to the plugin directory
        skills_paths: List of paths to search for skills (relative to plugin root)
        root_skill_name: Name to use if the plugin root itself is a skill

    Returns:
        List of skill names found
    """
    skills: list[str] = []

    # Check if plugin root has SKILL.md (plugin is the skill)
    if (plugin_path / "SKILL.md").exists():
        skills.append(root_skill_name)

    # Search each skills path
    for skills_base in skills_paths:
        skills_dir = plugin_path / skills_base
        if not skills_dir.exists() or not skills_dir.is_dir():
            continue

        # Find all subdirectories with SKILL.md
        for entry in skills_dir.iterdir():
            if entry.is_dir() and (entry / "SKILL.md").exists():
                skills.append(entry.name)

    return skills


def _discover_commands_in_plugin(
    plugin_path: Path, commands_paths: list[str]
) -> list[str]:
    """Discover all commands within a plugin directory.

    Looks for .md files in command directories.

    Args:
        plugin_path: Path to the plugin directory
        commands_paths: List of paths to search for commands (relative to plugin root)

    Returns:
        List of command names found (without .md extension)
    """
    commands: list[str] = []

    for cmd_base in commands_paths:
        cmd_dir = plugin_path / cmd_base
        if not cmd_dir.exists() or not cmd_dir.is_dir():
            continue

        # Find all .md files
        for entry in cmd_dir.iterdir():
            if entry.is_file() and entry.suffix == ".md":
                commands.append(entry.stem)

    return commands


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
    if (plugin_path / "SKILL.md").exists() and skill_name == root_skill_name:
        return str(plugin_path)

    # Search skills paths
    for skills_base in skills_paths:
        skill_dir = plugin_path / skills_base / skill_name
        if skill_dir.exists() and (skill_dir / "SKILL.md").exists():
            return str(skill_dir)

    return None


def _get_command_source_path(
    plugin_path: Path, command_name: str, commands_paths: list[str]
) -> str | None:
    """Get the full path to a command within a plugin.

    Args:
        plugin_path: Path to the plugin directory
        command_name: Name of the command (without .md extension)
        commands_paths: List of paths to search for commands

    Returns:
        Full path to command file, or None if not found
    """
    for cmd_base in commands_paths:
        cmd_file = plugin_path / cmd_base / f"{command_name}.md"
        if cmd_file.exists():
            return str(cmd_file)

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
    exclude_commands: list[str] = []
    exclude_agents: list[str] = []
    target_agents: list[str] = []

    if isinstance(plugin_spec, str):
        plugin_name = plugin_spec
        explicit_path = None
    else:
        plugin_name = plugin_spec.get("name", "")
        explicit_path = plugin_spec.get("path")
        exclude_skills = list(plugin_spec.get("exclude_skills", []))
        exclude_commands = list(plugin_spec.get("exclude_commands", []))
        exclude_agents = list(plugin_spec.get("exclude_agents", []))
        target_agents = list(plugin_spec.get("target_agents", []))

    # If explicit path, use it directly
    if explicit_path:
        plugin_path = repo_path / explicit_path.lstrip("./")
        plugin_json = _load_plugin_json(plugin_path)

        # Infer name from path if not provided
        if not plugin_name:
            plugin_name = plugin_path.name

        config = PluginConfig(
            name=plugin_name,
            source_path=explicit_path,
            skills_paths=_get_skills_paths(plugin_json or {}),
            commands_paths=_get_commands_paths(plugin_json or {}),
            agents_paths=_get_agents_paths(plugin_json or {}),
        )
        return ResolvedPlugin(
            config=config,
            plugin_path=plugin_path,
            exclude_skills=exclude_skills,
            exclude_commands=exclude_commands,
            exclude_agents=exclude_agents,
            target_agents=target_agents,
        )

    # Try marketplace lookup
    config = _find_plugin_in_marketplace(repo_path, plugin_name)
    if config:
        plugin_path = repo_path / config.source_path
        return ResolvedPlugin(
            config=config,
            plugin_path=plugin_path,
            exclude_skills=exclude_skills,
            exclude_commands=exclude_commands,
            exclude_agents=exclude_agents,
            target_agents=target_agents,
        )

    # Try standalone plugin
    config = _check_standalone_plugin(repo_path, plugin_name)
    if config:
        return ResolvedPlugin(
            config=config,
            plugin_path=repo_path,
            exclude_skills=exclude_skills,
            exclude_commands=exclude_commands,
            exclude_agents=exclude_agents,
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
    exclude_commands: list[str] = []
    exclude_agents: list[str] = []
    target_agents: list[str] = []
    base_path = Path(local_path)

    if isinstance(plugin_spec, str):
        plugin_name = plugin_spec
        explicit_path = None
    else:
        plugin_name = plugin_spec.get("name", "")
        explicit_path = plugin_spec.get("path")
        exclude_skills = list(plugin_spec.get("exclude_skills", []))
        exclude_commands = list(plugin_spec.get("exclude_commands", []))
        exclude_agents = list(plugin_spec.get("exclude_agents", []))
        target_agents = list(plugin_spec.get("target_agents", []))

    # Determine plugin path
    if explicit_path:
        plugin_path = base_path / explicit_path.lstrip("./")
        if not plugin_name:
            plugin_name = plugin_path.name
    else:
        # For local, assume plugins/{name} structure
        plugin_path = base_path / "plugins" / plugin_name

    # If plugin path doesn't exist, try base_path directly (for standalone)
    if not plugin_path.exists():
        plugin_path = base_path

    plugin_json = _load_plugin_json(plugin_path)

    config = PluginConfig(
        name=plugin_name,
        source_path=str(plugin_path),
        skills_paths=_get_skills_paths(plugin_json or {}),
        commands_paths=_get_commands_paths(plugin_json or {}),
        agents_paths=_get_agents_paths(plugin_json or {}),
    )

    return ResolvedPlugin(
        config=config,
        plugin_path=plugin_path,
        exclude_skills=exclude_skills,
        exclude_commands=exclude_commands,
        exclude_agents=exclude_agents,
        target_agents=target_agents,
    )


def agent_harness_build_plugin_resources(
    sources: list[SourceConfig], cache_dir: str
) -> dict[str, list[dict[str, Any]]]:
    """Build lists of skills, commands, and agents from plugin-based sources config.

    Args:
        sources: List of source configs (git repos or local paths)
        cache_dir: Path to the cache directory for git repos

    Returns:
        Dict with 'skills', 'commands', and 'agents' keys for Ansible/Jinja2
    """
    skills: list[ResourceInfo] = []
    commands: list[ResourceInfo] = []
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

                # For git sources, use repo name for root-level skills
                root_skill_name = repo.split("/")[-1]

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
                            )
                        )

                # Discover and add commands
                discovered_commands = _discover_commands_in_plugin(
                    plugin_path, config.commands_paths
                )
                for cmd_name in discovered_commands:
                    if cmd_name in resolved.exclude_commands:
                        continue
                    source_path = _get_command_source_path(
                        plugin_path, cmd_name, config.commands_paths
                    )
                    if source_path:
                        commands.append(
                            ResourceInfo(
                                name=cmd_name,
                                source=source_path,
                                origin=repo,
                                target_agents=resolved.target_agents,
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
                            )
                        )

                # Discover and add commands
                discovered_commands = _discover_commands_in_plugin(
                    plugin_path, config.commands_paths
                )
                for cmd_name in discovered_commands:
                    if cmd_name in resolved.exclude_commands:
                        continue
                    source_path = _get_command_source_path(
                        plugin_path, cmd_name, config.commands_paths
                    )
                    if source_path:
                        commands.append(
                            ResourceInfo(
                                name=cmd_name,
                                source=source_path,
                                origin="local",
                                target_agents=resolved.target_agents,
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
                            )
                        )

    return PluginResources(skills=skills, commands=commands, agents=agents).to_dict()


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


class FilterModule:
    """Ansible filter plugin for agent harness."""

    def filters(self) -> dict[str, object]:
        return {
            "agent_harness_build_plugin_resources": agent_harness_build_plugin_resources,
            "agent_harness_get_git_sources": agent_harness_get_git_sources,
            "agent_harness_filter_resources": agent_harness_filter_resources,
        }
