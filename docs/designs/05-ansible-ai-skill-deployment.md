# Ansible Agent Harness Role

## Problem Statement

AI coding agents (Claude Code, Amp, OpenCode, Codex) each have their own directory structures, file formats, and quirks for skills, commands, and subagents. Currently:

- Skills are scattered across unmanaged directories, a separate git repo (`thurstons-skills`), and third-party marketplaces
- Each agent needs its own translation (OpenCode wants lowercase names, different MCP formats, etc.)
- No automation exists to deploy a skill source to multiple agents at once

Bridle (github.com/neiii/bridle) solves this with a Rust runtime that translates between agents, but it's a separate tool with its own profile management. We want the same translation intelligence built into our existing Ansible automation.

## Goals

1. **Single role**: `agent_harness` role that deploys skills/commands/agents to supported AI agents
2. **Claude Code as source of truth**: All resources use Claude Code format; translate to other agents
3. **Agent-aware translation**: Handle naming conventions, path quirks, MCP format differences
4. **Idempotent**: Re-running produces no changes if already deployed
5. **Composable**: Works with existing chezmoi role for dotfiles, doesn't conflict

## Non-Goals

- Runtime profile switching (bridle's main feature) — we want static deployment
- VSCode/Cursor support (`.agent.md` format is too different)
- Goose support (not needed)
- Dynamic MCP loading (Amp/OpenCode support this but we'll use static deployment)

## Phased Approach

### Phase 1: Claude Code Only (MVP)

Deploy skills, commands, and agents to Claude Code. No translation needed — it's the source format.

### Phase 2: Add Amp

Amp uses nearly identical formats to Claude. Minor differences:

- MCP config in `settings.json` instead of `.mcp.json`
- No agents/subagents support

### Phase 3: Add OpenCode

OpenCode requires translation:

- Lowercase + dash names for directories
- Singular directory names (`skill/` not `skills/`)
- Different MCP format (array commands, `{env:VAR}` syntax)
- Agent color/tools field normalization

### Phase 4: Add Codex

Codex is similar to Claude but with limited features (skills only, no commands/agents).

---

## Agent Reference

### Directory Structures

| Agent    | Config Root           | Skills                      | Commands                      | Agents/Subagents            | Instructions |
| -------- | --------------------- | --------------------------- | ----------------------------- | --------------------------- | ------------ |
| Claude   | `~/.claude/`          | `~/.claude/skills/`         | `~/.claude/commands/`         | `~/.claude/agents/`         | `CLAUDE.md`  |
| Amp      | `~/.config/amp/`      | `~/.config/amp/skills/`     | `~/.config/amp/commands/`     | N/A                         | `AGENTS.md`  |
| OpenCode | `~/.config/opencode/` | `~/.config/opencode/skill/` | `~/.config/opencode/command/` | `~/.config/opencode/agent/` | `AGENTS.md`  |
| Codex    | `~/.codex/`           | `~/.codex/skills/`          | N/A                           | N/A                         | `AGENTS.md`  |

**Key difference**: OpenCode uses **singular** directory names (`skill/`, `command/`, `agent/`) while all others use plural.

### Agent Quirks

| Agent    | Naming Rules                | MCP Format               | MCP Key          | Special Requirements                             |
| -------- | --------------------------- | ------------------------ | ---------------- | ------------------------------------------------ |
| Claude   | Preserve original case      | `.mcp.json` (JSON)       | `mcpServers`     | **Source format**; env: `${VAR}`                 |
| Amp      | Preserve original case      | `settings.json` (JSON)   | `amp.mcpServers` | Skill mcp.json merged into global; env: `${VAR}` |
| OpenCode | **Lowercase + dashes only** | `opencode.jsonc` (JSONC) | `mcp`            | Singular dirs; env: `{env:VAR}`; cmd=array       |
| Codex    | Preserve original case      | Unknown                  | Unknown          | Limited testing                                  |

### Claude Code Format (Source of Truth)

#### Skills

Directory with `SKILL.md` and optional supporting files:

```
my-skill/
├── SKILL.md
├── mcp.json        # Optional: MCP tool definitions
└── scripts/        # Optional: Supporting scripts
    └── helper.sh
```

SKILL.md with YAML frontmatter:

```markdown
---
name: my-skill
description: Does something useful
---

# My Skill

Instructions for the agent...
```

#### Commands

Single markdown file with optional frontmatter:

```markdown
---
name: gc
description: Generate a git commit message from staged changes
---

Analyze the staged changes and generate a descriptive commit message...
```

#### Agents (Subagents/Personas)

Markdown file with YAML frontmatter:

```markdown
---
name: code-reviewer
description: Reviews staged changes before commit
color: pink
---

You are a senior software engineer...
```

#### MCP Configuration

Skill-bundled `mcp.json`:

```json
{
  "tmux": {
    "command": "npx",
    "args": ["-y", "tmux-mcp"],
    "env": { "DEBUG": "${MY_VAR}" }
  }
}
```

---

## Design

### Role Structure

```
ansible/roles/agent_harness/
├── defaults/
│   └── main.yml              # Default variables
├── tasks/
│   ├── main.yml              # Entry point
│   ├── deploy_skills.yml     # Deploy all skills
│   ├── deploy_commands.yml   # Deploy all commands
│   ├── deploy_agents.yml     # Deploy all agents
│   └── merge_mcp.yml         # Merge skill mcp.json into agent config
├── vars/
│   └── agents.yml            # Agent-specific paths and quirks
└── filter_plugins/
    └── harness_filters.py    # Custom filters for translation
```

### Variables

#### Agent Configuration (`vars/agents.yml`)

```yaml
---
harness_agents:
  claude:
    config_root: "{{ ansible_env.HOME }}/.claude"
    skills_dir: "{{ ansible_env.HOME }}/.claude/skills"
    commands_dir: "{{ ansible_env.HOME }}/.claude/commands"
    agents_dir: "{{ ansible_env.HOME }}/.claude/agents"
    mcp_file: "{{ ansible_env.HOME }}/.claude/.mcp.json"
    mcp_format: json
    mcp_key: mcpServers
    mcp_env_format: "${VAR}"
    mcp_command_format: separate # command + args separate fields
    name_transform: preserve
    transform_content: false
    instructions_file: CLAUDE.md

  amp:
    config_root: "{{ ansible_env.HOME }}/.config/amp"
    skills_dir: "{{ ansible_env.HOME }}/.config/amp/skills"
    commands_dir: "{{ ansible_env.HOME }}/.config/amp/commands"
    agents_dir: null # Amp doesn't support agents
    mcp_file: "{{ ansible_env.HOME }}/.config/amp/settings.json"
    mcp_format: json
    mcp_key: "amp.mcpServers"
    mcp_env_format: "${VAR}"
    mcp_command_format: separate
    name_transform: preserve
    transform_content: false
    instructions_file: AGENTS.md

  opencode:
    config_root: "{{ ansible_env.HOME }}/.config/opencode"
    skills_dir: "{{ ansible_env.HOME }}/.config/opencode/skill" # SINGULAR
    commands_dir: "{{ ansible_env.HOME }}/.config/opencode/command" # SINGULAR
    agents_dir: "{{ ansible_env.HOME }}/.config/opencode/agent" # SINGULAR
    mcp_file: "{{ ansible_env.HOME }}/.config/opencode/opencode.jsonc"
    mcp_format: jsonc
    mcp_key: mcp
    mcp_env_format: "{env:VAR}"
    mcp_command_format: array # command is array with args merged
    mcp_type_required: true # must include type: local/remote
    name_transform: lowercase_dash
    transform_content: true # rewrite frontmatter for OpenCode
    instructions_file: AGENTS.md

  codex:
    config_root: "{{ ansible_env.HOME }}/.codex"
    skills_dir: "{{ ansible_env.HOME }}/.codex/skills"
    commands_dir: null # Codex doesn't support commands
    agents_dir: null # Codex doesn't support agents
    mcp_file: null # Unknown
    mcp_format: null
    mcp_key: null
    name_transform: preserve
    transform_content: false
    instructions_file: AGENTS.md
```

#### Role Variables (`defaults/main.yml`)

```yaml
---
# Which agents to deploy to
harness_target_agents:
  - claude

# Path to resources directory (contains skills/, commands/, agents/)
harness_resources_dir: "{{ playbook_dir }}/../ai-resources"

# Git-sourced skills
# Short form: skill name auto-discovers at plugins/{name}/skills/{name}/SKILL.md
# Long form: explicit path for non-standard layouts
harness_git_skills: []
#   - repo: anthropics/claude-code
#     skills:
#       - frontend-design                    # short form
#       - memory
#       - name: custom-name                  # long form
#         path: plugins/some-plugin/skills/actual-skill
#
#   - repo: neiii/bridle
#     skills:
#       - path: skills/tmux-interactive      # explicit path only

# Git update behavior
# false (default): clone if missing, never pull (fast, predictable)
# true: always pull latest (use with -e harness_update_git=true)
harness_update_git: false

# Where to cache git repos
harness_cache_dir: "{{ ansible_env.HOME }}/.cache/ansiblonomicon-harness"
```

### Task Flow

#### Main Entry Point (`tasks/main.yml`)

```yaml
---
- name: Include agent configuration
  ansible.builtin.include_vars: agents.yml

- name: Validate target agents
  ansible.builtin.assert:
    that: item in harness_agents
    fail_msg: "Unknown agent: {{ item }}"
  loop: "{{ harness_target_agents }}"

- name: Deploy skills
  ansible.builtin.include_tasks: deploy_skills.yml

- name: Deploy commands
  ansible.builtin.include_tasks: deploy_commands.yml

- name: Deploy agents
  ansible.builtin.include_tasks: deploy_agents.yml
```

#### Deploy Skills (`tasks/deploy_skills.yml`)

```yaml
---
- name: Find local skills
  ansible.builtin.find:
    paths: "{{ harness_resources_dir }}/skills"
    patterns: "SKILL.md"
    recurse: true
    file_type: file
  register: found_skills
  delegate_to: localhost

- name: Deploy each skill to each target agent
  ansible.builtin.include_tasks: deploy_single_skill.yml
  vars:
    skill_path: "{{ skill_item.path | dirname }}"
    skill_name: "{{ skill_item.path | dirname | basename }}"
  loop: "{{ found_skills.files }}"
  loop_control:
    loop_var: skill_item
    label: "{{ skill_item.path | dirname | basename }}"
```

#### Deploy Single Skill (`tasks/deploy_single_skill.yml`)

```yaml
---
- name: Deploy skill to each target agent
  block:
    - name: Get agent config
      ansible.builtin.set_fact:
        agent_config: "{{ harness_agents[agent_name] }}"

    - name: Skip if agent doesn't support skills
      ansible.builtin.debug:
        msg: "Skipping {{ agent_name }} - no skills support"
      when: agent_config.skills_dir is none

    - name: Compute target skill name
      ansible.builtin.set_fact:
        target_skill_name: "{{ skill_name | harness_transform_name(agent_config.name_transform) }}"
      when: agent_config.skills_dir is not none

    - name: Ensure agent skills directory exists
      ansible.builtin.file:
        path: "{{ agent_config.skills_dir }}"
        state: directory
        mode: "0755"
      when: agent_config.skills_dir is not none

    - name: Sync skill directory
      ansible.posix.synchronize:
        src: "{{ skill_path }}/"
        dest: "{{ agent_config.skills_dir }}/{{ target_skill_name }}/"
        delete: true
        recursive: true
      delegate_to: "{{ inventory_hostname }}"
      when: agent_config.skills_dir is not none

    - name: Transform SKILL.md content if needed
      when:
        - agent_config.skills_dir is not none
        - agent_config.transform_content | default(false)
      block:
        - name: Read SKILL.md
          ansible.builtin.slurp:
            src: "{{ agent_config.skills_dir }}/{{ target_skill_name }}/SKILL.md"
          register: skill_content

        - name: Transform and write SKILL.md
          ansible.builtin.copy:
            content: "{{ skill_content.content | b64decode | harness_transform_skill(target_skill_name) }}"
            dest: "{{ agent_config.skills_dir }}/{{ target_skill_name }}/SKILL.md"
            mode: "0644"

    - name: Merge MCP configuration if present
      ansible.builtin.include_tasks: merge_mcp.yml
      vars:
        mcp_source: "{{ skill_path }}/mcp.json"
      when:
        - agent_config.skills_dir is not none
        - agent_config.mcp_file is not none

  loop: "{{ harness_target_agents }}"
  loop_control:
    loop_var: agent_name
    label: "{{ skill_name }} -> {{ agent_name }}"
```

### Custom Filter Plugin (`filter_plugins/harness_filters.py`)

```python
"""Custom Jinja2 filters for agent harness deployment."""

import re


# Color name to hex mapping (from bridle)
COLOR_MAP = {
    "red": "#FF0000", "green": "#00FF00", "blue": "#0000FF",
    "yellow": "#FFFF00", "orange": "#FFA500", "purple": "#800080",
    "cyan": "#00FFFF", "magenta": "#FF00FF", "white": "#FFFFFF",
    "black": "#000000", "gray": "#808080", "grey": "#808080",
    "pink": "#FFC0CB", "brown": "#A52A2A", "lime": "#00FF00",
    "navy": "#000080", "teal": "#008080", "olive": "#808000",
    "maroon": "#800000", "aqua": "#00FFFF", "silver": "#C0C0C0",
    "gold": "#FFD700",
}


def harness_sanitize_name(name: str) -> str:
    """Sanitize name for OpenCode (lowercase + dashes only)."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name


def harness_transform_name(name: str, transform: str) -> str:
    """Transform name according to agent requirements."""
    if transform == "lowercase_dash":
        return harness_sanitize_name(name)
    return name  # preserve


def harness_transform_skill(content: str, sanitized_name: str) -> str:
    """Transform SKILL.md for OpenCode (rewrite frontmatter)."""
    if not content.strip().startswith("---"):
        return f"---\nname: {sanitized_name}\ndescription: Skill\n---\n{content}"

    parts = content.split("---", 2)
    if len(parts) < 3:
        return content

    frontmatter = parts[1]
    body = parts[2]

    new_lines = []
    found_name = False
    found_description = False

    for line in frontmatter.strip().split("\n"):
        stripped = line.strip()
        if stripped.startswith("name:"):
            new_lines.append(f"name: {sanitized_name}")
            found_name = True
            continue
        if stripped.startswith("description:"):
            found_description = True
        new_lines.append(line)

    if not found_name:
        new_lines.insert(0, f"name: {sanitized_name}")
    if not found_description:
        new_lines.insert(1, "description: Skill")

    return f"---\n{chr(10).join(new_lines)}\n---{body}"


def harness_transform_agent(content: str, sanitized_name: str) -> str:
    """Transform agent.md for OpenCode (color to hex, tools normalization)."""
    if not content.strip().startswith("---"):
        return content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return content

    frontmatter = parts[1]
    body = parts[2]

    new_lines = []
    for line in frontmatter.strip().split("\n"):
        stripped = line.strip()

        # Handle name field
        if stripped.startswith("name:"):
            new_lines.append(f"name: {sanitized_name}")
            continue

        # Handle color field - convert names to hex
        if stripped.startswith("color:"):
            color_value = stripped.split(":", 1)[1].strip().strip("\"'")
            if color_value.lower() in COLOR_MAP:
                new_lines.append(f'color: "{COLOR_MAP[color_value.lower()]}"')
                continue

        # Handle tools field - normalize to wildcard
        if stripped.startswith("tools:"):
            value = stripped.split(":", 1)[1].strip()
            if value and not value.startswith("{") and value not in ("|", ">"):
                new_lines.append("tools:")
                new_lines.append('  "*": true')
                continue

        new_lines.append(line)

    return f"---\n{chr(10).join(new_lines)}\n---{body}"


def harness_transform_mcp_server(server: dict, agent_config: dict) -> dict:
    """Transform MCP server config for target agent."""
    cmd_format = agent_config.get("mcp_command_format", "separate")
    env_format = agent_config.get("mcp_env_format", "${VAR}")
    type_required = agent_config.get("mcp_type_required", False)

    result = {}
    command = server.get("command", "")
    args = server.get("args", [])

    if cmd_format == "array":
        # OpenCode: command is array
        result["command"] = [command] + args if command else args
        result["type"] = "local"
        result["enabled"] = True
    else:
        # Claude/Amp: separate fields
        result["command"] = command
        if args:
            result["args"] = args

    # Handle environment variables
    env = server.get("env", {})
    if env:
        transformed_env = {}
        for key, value in env.items():
            if env_format == "{env:VAR}" and value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1]
                transformed_env[key] = f"{{env:{var_name}}}"
            else:
                transformed_env[key] = value

        if cmd_format == "array":
            result["environment"] = transformed_env
        else:
            result["env"] = transformed_env

    if type_required and "type" not in result:
        result["type"] = "local"

    return result


def harness_mcp_merge(skill_mcp: dict, agent_config: dict) -> dict:
    """Merge skill MCP config into agent format."""
    mcp_key = agent_config.get("mcp_key", "mcpServers")

    transformed = {}
    for name, server in skill_mcp.items():
        transformed[name] = harness_transform_mcp_server(server, agent_config)

    if mcp_key == "mcpServers":
        return {"mcpServers": transformed}
    elif mcp_key == "amp.mcpServers":
        return {"amp": {"mcpServers": transformed}}
    elif mcp_key == "mcp":
        return {"mcp": transformed}
    else:
        return transformed


class FilterModule:
    """Ansible filter plugin for agent harness."""

    def filters(self):
        return {
            "harness_sanitize_name": harness_sanitize_name,
            "harness_transform_name": harness_transform_name,
            "harness_transform_skill": harness_transform_skill,
            "harness_transform_agent": harness_transform_agent,
            "harness_transform_mcp_server": harness_transform_mcp_server,
            "harness_mcp_merge": harness_mcp_merge,
        }
```

---

## Usage

### Resources Directory Structure

```
ansible/ai-resources/
├── skills/
│   ├── git-commit-helper/
│   │   └── SKILL.md
│   ├── truenas-docker-ops/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── docker-exec.sh
│   └── tmux-interactive-sessions/
│       ├── SKILL.md
│       └── mcp.json
│
├── commands/
│   ├── gc.md
│   └── system-architect.md
│
└── agents/
    └── code-reviewer.md
```

### Playbook Integration

```yaml
# ansible/playbooks/local.yml
- name: Deploy AI agent resources
  ansible.builtin.include_role:
    name: agent_harness
  vars:
    harness_target_agents:
      - claude # Phase 1: Claude only
      # - amp       # Phase 2
      # - opencode  # Phase 3
      # - codex     # Phase 4
  tags: [agent-harness]
```

### Phase 1 Deployment (Claude Only)

```yaml
harness_target_agents:
  - claude
```

Results in:

```
~/.claude/
├── skills/
│   ├── git-commit-helper/
│   │   └── SKILL.md
│   ├── truenas-docker-ops/
│   │   ├── SKILL.md
│   │   └── scripts/
│   └── tmux-interactive-sessions/
│       ├── SKILL.md
│       └── mcp.json
├── commands/
│   ├── gc.md
│   └── system-architect.md
├── agents/
│   └── code-reviewer.md
└── .mcp.json  # Updated with tmux server
```

---

## Migration Plan

### Phase 1: Claude Code (MVP)

1. Create `ansible/roles/agent_harness/` structure
2. Create `ansible/ai-resources/` with skills/commands/agents from current locations
3. Implement basic sync for Claude (no translation needed)
4. Test: Skills appear in Claude Code, MCP config merged correctly

### Phase 2: Add Amp

1. Add Amp to `harness_agents` config
2. Handle MCP file difference (`settings.json` vs `.mcp.json`)
3. Skip agents (Amp doesn't support them)
4. Test: Same skills work in both Claude and Amp

### Phase 3: Add OpenCode

1. Add OpenCode to `harness_agents` config
2. Implement name transformation (lowercase_dash)
3. Implement content transformation (SKILL.md frontmatter, agent colors)
4. Implement MCP format translation
5. Test: Skills deploy with correct transformations

### Phase 4: Add Codex + Cleanup

1. Add Codex (skills only)
2. Delete `thurstons-skills` repo
3. Remove Claude marketplace config
4. Update documentation

---

## Appendix: Translation Reference

### OpenCode Transformations

| Source (Claude)           | Target (OpenCode)                   |
| ------------------------- | ----------------------------------- |
| `skills/My-Skill/`        | `skill/my-skill/`                   |
| `commands/gc.md`          | `command/gc.md`                     |
| `agents/code-reviewer.md` | `agent/code-reviewer.md`            |
| `name: My-Skill`          | `name: my-skill`                    |
| `color: pink`             | `color: "#FFC0CB"`                  |
| `"command": "npx"`        | `"command": ["npx", "-y", "..."]`   |
| `"env": {"X": "${VAR}"}`  | `"environment": {"X": "{env:VAR}"}` |

### Directory Names by Agent

| Agent    | Skills | Commands | Agents |
| -------- | ------ | -------- | ------ |
| Claude   | skills | commands | agents |
| Amp      | skills | commands | —      |
| OpenCode | skill  | command  | agent  |
| Codex    | skills | —        | —      |
