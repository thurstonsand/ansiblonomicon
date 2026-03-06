# Ansible Agent Harness Role

## Problem Statement

AI coding agents (Claude Code, Amp, OpenCode, Codex) each have their own directory structures, file formats, and quirks for skills, commands, and subagents. Currently:

- Skills were scattered across unmanaged directories and third-party marketplaces (now consolidated in `agents/` directory)
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

## Implementation Status

### Phase 1: Claude Code Only (MVP) — **COMPLETE**

| Feature                                  | Status         | Notes                                             |
| ---------------------------------------- | -------------- | ------------------------------------------------- |
| Role structure                           | ✅ Done        | `ansible/roles/agent_harness/`                    |
| Git source cloning                       | ✅ Done        | Clones repos to cache, supports `pull` option     |
| Local source support                     | ✅ Done        | Direct path to local skills                       |
| Skill discovery (marketplace.json)       | ✅ Done        | Finds skills in Claude plugin marketplaces        |
| Skill discovery (standalone plugin.json) | ✅ Done        | Finds skills in single-plugin repos               |
| Skill sync to Claude                     | ✅ Done        | rsync with checksum, excludes .git/.claude-plugin |
| Commands deployment                      | ✅ Done        | Sync markdown files from commands/ directories    |
| Agents/subagents deployment              | ✅ Done        | Sync markdown files from agents/ directories      |
| Orphan cleanup                           | ✅ Done        | Remove skills/commands/agents not in sources      |
| MCP config merging                       | ⏸️ Deferred   | MCP is plugin-scoped, not skill-scoped            |
| LSP server deployment                    | ⏸️ Deferred   | LSP is plugin-scoped, not skill-scoped            |
| Unit tests                               | ✅ Done        | 97 tests for filter plugins                       |

### Phase 2: Add Amp — **COMPLETE**

| Feature                           | Status       | Notes                                                |
| --------------------------------- | ------------ | ---------------------------------------------------- |
| Amp agent config                  | ✅ Done      | Added to `vars/agents.yml`                           |
| Per-agent targeting               | ✅ Done      | `target_agents` field in plugin spec                 |
| Skills deployment to Amp          | ✅ Done      | Same format as Claude, rsync works unchanged         |
| Commands deployment to Amp        | ✅ Done      | Amp uses same commands dir structure                 |
| Skip agents for Amp               | ✅ Done      | `agents_dir: null` skips deployment/cleanup          |
| Skill-bundled MCP (Amp-only)      | ✅ Done      | rsync copies mcp.json, Amp reads natively            |
| thurstons-skills migration        | ✅ Done      | Migrated to `agents/claude/`, deprecated old repo    |

### Phase 3: Add Codex — **COMPLETE**

| Feature                           | Status       | Notes                                                |
| --------------------------------- | ------------ | ---------------------------------------------------- |
| Codex agent config                | ✅ Done      | Added to `vars/agents.yml`                           |
| Skills deployment to Codex        | ✅ Done      | Same SKILL.md format, rsync works unchanged          |
| Commands deployment to Codex      | ✅ Done      | Codex uses `~/.codex/prompts/` ("custom prompts")    |
| Skip agents for Codex             | ✅ Done      | `agents_dir: null` skips deployment/cleanup          |

### Phase 4: Add OpenCode — **COMPLETE**

| Feature                           | Status       | Notes                                                |
| --------------------------------- | ------------ | ---------------------------------------------------- |
| OpenCode agent config             | ✅ Done      | Added to `vars/agents.yml`                           |
| Skills deployment to OpenCode     | ✅ Done      | `~/.config/opencode/skill/` (singular)               |
| Commands deployment to OpenCode   | ✅ Done      | `~/.config/opencode/command/` (singular)             |
| Agents deployment to OpenCode     | ✅ Done      | `~/.config/opencode/agent/` (singular)               |
| Name transformation               | ⏸️ Deferred | OpenCode requires lowercase-dash names; rsync copies as-is for now |

---

## Current Implementation

### Role Structure

```
ansible/roles/agent_harness/
├── defaults/
│   └── main.yml                   # Default variables
├── filter_plugins/
│   └── harness_filters.py         # Resource discovery and source parsing
├── tasks/
│   ├── main.yml                   # Entry point
│   ├── clone_git_repos.yml        # Clone/update git sources
│   ├── deploy_skills.yml          # Deploy skills to target agent
│   ├── deploy_single_skill.yml    # Sync individual skill
│   ├── deploy_commands.yml        # Deploy commands to target agent
│   ├── deploy_single_command.yml  # Sync individual command
│   ├── deploy_agents.yml          # Deploy agents to target agent
│   ├── deploy_single_agent.yml    # Sync individual agent
│   └── cleanup_orphans.yml        # Remove unmanaged skills/commands/agents
├── tests/
│   ├── conftest.py                # pytest path setup
│   └── test_harness_filters.py    # Unit tests for filters
└── vars/
    └── agents.yml                 # Agent-specific paths and quirks
```

### Configuration

#### Sources Configuration (`ansible/config.yml`)

```yaml
agent_harness_sources:
  # Git sources - clone from GitHub
  - repo: anthropics/claude-code
    pull: true # Update on each run (default: true)
    skills:
      - frontend-design # short form: auto-discover
      - name: custom-name # long form: explicit path
        path: plugins/some-plugin/skills/actual-skill

  # Local sources - use existing directory
  - local: "{{ playbook_dir }}/../ai-resources"
    skills:
      - my-skill # short form: skills/{name}/
      - name: another-skill
        path: custom/path/to/skill
```

#### Role Defaults (`defaults/main.yml`)

```yaml
# Which agents to deploy to
agent_harness_target_agents:
  - claude

# Sources for skills (see above)
agent_harness_sources: []

# Git update behavior (default: true = always pull)
agent_harness_update: true

# Where to cache git repos
agent_harness_cache_dir: "{{ ansible_facts.env.HOME }}/.cache/ansiblonomicon-harness"
```

#### Agent Configuration (`vars/agents.yml`)

All five agents are configured:

```yaml
agent_harness_agents:
  claude:
    config_root: "{{ ansible_facts.env.HOME }}/.claude"
    skills_dir: "{{ ansible_facts.env.HOME }}/.claude/skills"
    commands_dir: "{{ ansible_facts.env.HOME }}/.claude/commands"
    agents_dir: "{{ ansible_facts.env.HOME }}/.claude/agents"
    mcp_file: "{{ ansible_facts.env.HOME }}/.claude/.mcp.json"
    mcp_format: json
    mcp_key: mcpServers
    mcp_env_format: "${VAR}"
    mcp_command_format: separate
    name_transform: preserve
    transform_content: false
    instructions_file: CLAUDE.md
    supports_skill_mcp: false

  amp:
    config_root: "{{ ansible_facts.env.HOME }}/.config/amp"
    skills_dir: "{{ ansible_facts.env.HOME }}/.config/amp/skills"
    commands_dir: "{{ ansible_facts.env.HOME }}/.config/amp/commands"
    agents_dir: null  # Amp does not support user-defined subagents
    mcp_file: "{{ ansible_facts.env.HOME }}/.config/amp/settings.json"
    mcp_format: json
    mcp_key: amp.mcpServers
    mcp_env_format: "${VAR}"
    mcp_command_format: separate
    name_transform: preserve
    transform_content: false
    instructions_file: AGENTS.md
    supports_skill_mcp: true  # Amp reads mcp.json from skill directories

  codex:
    config_root: "{{ ansible_facts.env.HOME }}/.codex"
    skills_dir: "{{ ansible_facts.env.HOME }}/.codex/skills"
    commands_dir: "{{ ansible_facts.env.HOME }}/.codex/prompts"  # Codex calls these "custom prompts"
    agents_dir: null  # Codex does not support user-defined subagents
    mcp_file: "{{ ansible_facts.env.HOME }}/.codex/config.toml"
    mcp_format: toml
    mcp_key: mcp_servers
    mcp_env_format: literal  # Codex uses literal env var strings
    mcp_command_format: separate
    name_transform: preserve
    transform_content: false
    instructions_file: AGENTS.md
    supports_skill_mcp: false

  opencode:
    config_root: "{{ ansible_facts.env.HOME }}/.config/opencode"
    skills_dir: "{{ ansible_facts.env.HOME }}/.config/opencode/skill"   # SINGULAR
    commands_dir: "{{ ansible_facts.env.HOME }}/.config/opencode/command"  # SINGULAR
    agents_dir: "{{ ansible_facts.env.HOME }}/.config/opencode/agent"   # SINGULAR
    mcp_file: "{{ ansible_facts.env.HOME }}/.config/opencode/opencode.json"
    mcp_format: json
    mcp_key: mcp
    mcp_env_format: "{env:VAR}"  # OpenCode uses {env:VAR} syntax
    mcp_command_format: array    # command is an array: ["cmd", "arg1", "arg2"]
    name_transform: lowercase_dash  # Names must be lowercase alphanumeric with single hyphen separators
    transform_content: false
    instructions_file: AGENTS.md
    supports_skill_mcp: false

  pi:
    config_root: "{{ ansible_facts.env.HOME }}/.pi/agent"
    skills_dir: "{{ ansible_facts.env.HOME }}/.pi/agent/skills"
    commands_dir: null
    agents_dir: null
    mcp_file: null
    mcp_format: json
    mcp_key: null
    mcp_env_format: "${VAR}"
    mcp_command_format: separate
    name_transform: preserve
    transform_content: false
    instructions_file: AGENTS.md
    supports_skill_mcp: false
```

### Filter Plugins

Two main filters implemented:

| Filter                                 | Purpose                                                                                                                             |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `agent_harness_get_git_sources`        | Extract git sources from sources list, normalize with defaults                                                                      |
| `agent_harness_build_plugin_resources` | Resolve all plugin specs to concrete paths for skills, commands, and agents (handles marketplace.json, plugin.json, explicit paths) |

### Skill Discovery Logic

The filter plugin implements Claude's plugin discovery protocol:

1. **Marketplace repos** (e.g., `anthropics/claude-code`):

   - Check `.claude-plugin/marketplace.json` for plugin registry
   - Look up plugin by name, get source path
   - Handle `strict: true/false` for plugin.json merging
   - Search `skills_paths` for matching skill

2. **Standalone plugin repos**:

   - Check `.claude-plugin/plugin.json` at repo root
   - Match plugin name, search skills paths

3. **Explicit path** (long form):
   - Use provided path directly

---

## Remaining Work for Phase 1

### Nice to Have

1. **Dry-run mode**
   - Show what would be deployed without making changes

### Deferred

2. **MCP config merging** — MCP servers are a plugin-level feature, not skill-level. Since we deploy individual skills (not full plugins), MCP doesn't cleanly map. Users should configure MCP servers separately via `claude mcp add`.

3. **LSP server deployment** — LSP servers are also plugin-scoped (configured via `.lsp.json` or inline in `plugin.json`). Claude Code has no user-level LSP config outside the plugin system. Users should install LSP plugins from the official marketplace (`/plugin` → Discover → search "lsp").

---

## Agent Reference

### Directory Structures

| Agent    | Config Root           | Skills                      | Commands              | Agents/Subagents            | Instructions |
| -------- | --------------------- | --------------------------- | --------------------- | --------------------------- | ------------ |
| Claude   | `~/.claude/`          | `~/.claude/skills/`         | `~/.claude/commands/` | `~/.claude/agents/`         | `CLAUDE.md`  |
| Amp      | `~/.config/amp/`      | `~/.config/amp/skills/`     | `~/.config/amp/commands/` | N/A                      | `AGENTS.md`  |
| Codex    | `~/.codex/`           | `~/.codex/skills/`          | `~/.codex/prompts/`   | N/A                         | `AGENTS.md`  |
| OpenCode | `~/.config/opencode/` | `~/.config/opencode/skill/` | `~/.config/opencode/command/` | `~/.config/opencode/agent/` | `AGENTS.md`  |
| Pi       | `~/.pi/agent/`        | `~/.pi/agent/skills/`       | N/A                   | N/A                         | `AGENTS.md`  |

**Key difference**: OpenCode uses **singular** directory names (`skill/`, `command/`, `agent/`) while all others use plural.

### Agent Quirks

| Agent    | Naming Rules                | MCP Format             | MCP Key          | Special Requirements                             |
| -------- | --------------------------- | ---------------------- | ---------------- | ------------------------------------------------ |
| Claude   | Preserve original case      | `.mcp.json` (JSON)     | `mcpServers`     | **Source format**; env: `${VAR}`                 |
| Amp      | Preserve original case      | `settings.json` (JSON) | `amp.mcpServers` | Skill mcp.json merged into global; env: `${VAR}` |
| Codex    | Preserve original case      | `config.toml` (TOML)   | `mcp_servers`    | Commands in `prompts/`; env: literal strings     |
| OpenCode | **Lowercase + dashes only** | `opencode.json` (JSON) | `mcp`            | Singular dirs; env: `{env:VAR}`; cmd=array       |
| Pi       | Preserve original case      | None                   | N/A              | Skills only; no built-in commands, agents, or MCP |

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

## Usage

### Current Playbook Integration

```yaml
# ansible/playbooks/local.yml
- name: Deploy AI agent resources
  ansible.builtin.include_role:
    name: agent_harness
    apply:
      tags: ["agent-harness"]
  when: configure_agent_harness | default(true)
  tags: ["agent-harness"]
```

### Running

```bash
# Deploy skills
uv run poe local -t agent-harness

# Dry-run
uv run poe local -t agent-harness --check

# Force git pull even if pull: false
uv run poe local -t agent-harness -e agent_harness_update=true
```

---

## Migration Plan

### Phase 1: Claude Code (MVP) — Current

1. ✅ Create `ansible/roles/agent_harness/` structure
2. ✅ Implement git source cloning with plugin discovery
3. ✅ Implement skill sync for Claude
4. ✅ Implement commands deployment
5. ✅ Implement agents deployment
6. ✅ Implement orphan cleanup (skills/commands/agents)
7. ⬜ Implement MCP config merging
8. ⬜ Test: Skills/commands/agents appear in Claude Code, MCP config merged

### Phase 2: Add Amp — ✅ Complete

1. ✅ Add Amp to `agent_harness_agents` config
2. ✅ Handle MCP file difference (`settings.json` vs `.mcp.json`)
3. ✅ Skip agents (Amp doesn't support them)
4. ✅ Test: Same skills work in both Claude and Amp

### Phase 3: Add Codex — ✅ Complete

1. ✅ Add Codex to `agent_harness_agents` config
2. ✅ Skills deploy to `~/.codex/skills/`
3. ✅ Commands deploy to `~/.codex/prompts/` ("custom prompts")
4. ✅ Skip agents (Codex doesn't support them)

### Phase 4: Add OpenCode — ✅ Complete

1. ✅ Add OpenCode to `agent_harness_agents` config
2. ⏸️ Implement name transformation (lowercase_dash) — Deferred, rsync copies as-is
3. ⏸️ Implement content transformation — Deferred, SKILL.md format is compatible
4. ⏸️ Implement MCP format translation — Deferred, MCP configured separately
5. ✅ Skills/commands/agents deploy to singular directories

### Phase 5: Add Pi — ✅ Complete

1. ✅ Add Pi to `agent_harness_agents` config
2. ✅ Deploy skills to `~/.pi/agent/skills/`
3. ✅ Deploy `AGENTS.md` instructions to `~/.pi/agent/AGENTS.md`
4. ✅ Skip commands and agents (Pi does not support user-defined equivalents)

### Phase 6: Cleanup — ✅ Complete

1. ✅ Migrated `thurstons-skills` repo to `agents/claude/`
2. ✅ Removed Claude marketplace config from chezmoi
3. ✅ Updated Codex/OpenCode universal-skills MCP to use `~/.claude/skills`
4. 🔲 Delete `thurstons-claude-skills` repo from GitHub (manual step)

---

## Appendix: Translation Reference (Future Phases)

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
| Codex    | skills | prompts  | —      |
| OpenCode | skill  | command  | agent  |
| Pi       | skills | —        | —      |
