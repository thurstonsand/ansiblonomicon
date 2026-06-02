---
name: amp-skill-creator
description: PRIMARY skill creator. Use this by default when creating ANY skill. If user explicitly asks for a "Claude skill", "Claude-compatible skill", or "universal skill", use write-a-skill instead. Handles Amp-specific features (mcp.json, OAuth, Amp frontmatter).
argument-hint: "[skill-name] [objective]"
---

# Amp Skill Creator

This skill covers Amp-specific features for skill creation. After reading this, **load the `write-a-skill` skill** and follow its workflow, applying the overrides at the end of this document.

---

## First: Ask Where to Install

Before creating a skill, **ask the user where they want it installed** (if they haven't already specified):

- `.agents/skills/` — workspace-local (project-specific)
- `~/.config/amp/skills/` — global user

---

## Amp-Specific Features

### Amp Frontmatter Fields

Beyond the required `name` and `description`, Amp supports:

```yaml
---
name: my-skill-name
description: What the skill does and when to use it
argument-hint: "[query]" # Shown in /skill-list (e.g., "[repo] [issue]")
disable-model-invocation: true # Hides from agent auto-detection (manual /skill only)
---
```

---

## Bundled MCP Servers

Skills can bundle MCP servers via `mcp.json` in the skill root:

```
skill-name/
├── SKILL.md
└── mcp.json
```

### mcp.json Format

```json
{
  "local-server-name": {
    "command": "npx",
    "args": ["-y", "some-mcp-server@latest"],
    "env": {
      "API_KEY": "${MY_API_KEY}"
    },
    "includeTools": ["tool_a", "tool_b", "navigate_*"]
  },
  "remote-server-name": {
    "url": "https://some-mcp-server.com/mcp",
    "headers": {
      "Authorization": "Bearer ${TOKEN}"
    },
    "includeTools": ["tool_a", "tool_b"]
  }
}
```

### Local Server Fields

| Field          | Required        | Description                           |
| -------------- | --------------- | ------------------------------------- |
| `command`      | Yes             | Command to run                        |
| `args`         | No              | Array of command arguments            |
| `env`          | No              | Environment variables for the server  |
| `includeTools` | **Recommended** | Glob patterns to filter exposed tools |

### Remote Server Fields

| Field          | Required        | Description                           |
| -------------- | --------------- | ------------------------------------- |
| `url`          | Yes             | URL of the MCP server                 |
| `headers`      | No              | Headers to send with requests         |
| `includeTools` | **Recommended** | Glob patterns to filter exposed tools |

### Environment Variables

Use `${VAR_NAME}` syntax in any field:

```json
{
  "my-server": {
    "command": "node",
    "args": ["${HOME}/scripts/mcp-server.js"],
    "env": {
      "API_KEY": "${SERVICE_API_KEY}"
    }
  }
}
```

### Always Filter Tools

MCP servers often expose many tools (20+ = thousands of tokens). **Always use `includeTools`:**

```json
{
  "includeTools": ["navigate_page", "take_screenshot", "click"]
}
```

Glob patterns supported: `["navigate_*", "click"]` or `["*"]` for all.

---

## Adding MCP Servers via CLI

Use `amp mcp add` to quickly generate MCP server config:

```sh
# Local server (command-based)
amp mcp add <name> -- <command> [args...]

# Local server with env vars
amp mcp add <name> --env KEY=VAL -- <command> [args...]

# Remote server (URL-based, auto-detects transport)
amp mcp add <name> <url>

# Remote server with headers
amp mcp add <name> --header "Authorization=Bearer <token>" <url>

# Add to workspace settings instead of global
amp mcp add <name> --workspace -- <command> [args...]
```

> **Note:** This command adds the server config to `~/.config/amp/settings.json` (or workspace settings with `--workspace`), not directly into a skill's `mcp.json`. After running, copy the relevant entry from settings into your skill's `mcp.json` file.

### Options

| Option             | Description                                                                 |
| ------------------ | --------------------------------------------------------------------------- |
| `--env KEY=VAL`    | Environment variables (repeatable)                                          |
| `--header KEY=VAL` | HTTP headers for URL-based servers (repeatable)                             |
| `--workspace`      | Add to workspace settings instead of global (`~/.config/amp/settings.json`) |

### Examples

```sh
# NPX-based server
amp mcp add context7 -- npx -y @upstash/context7-mcp

# Postgres with env vars
amp mcp add postgres --env PGUSER=myuser -- npx -y @modelcontextprotocol/server-postgres postgresql://localhost/mydb

# Remote with auth header
amp mcp add sourcegraph --header "Authorization=token <token>" https://sourcegraph.example.com/.api/mcp/v1

# Remote with OAuth (auto-triggers browser auth)
amp mcp add linear https://mcp.linear.app/sse

# Workspace-specific server
amp mcp add project-server --workspace -- npx -y @some/server
```

---

## Now: Load write-a-skill

**Load the `write-a-skill` skill now** and follow its workflow for creating the skill content. Apply these overrides during implementation:

---

## Overrides for write-a-skill

| write-a-skill Says                      | Amp Does Instead                                                          |
| --------------------------------------- | ------------------------------------------------------------------------- |
| Skill installs via Claude `skills/` dir | Use locations from "First: Ask Where to Install" above                    |
| `name` + `description` frontmatter only | Amp also supports `argument-hint`, `disable-model-invocation` (see above) |
| No MCP bundling guidance                | Bundle MCP servers via `mcp.json` (see above)                             |

**What to USE from write-a-skill:**

- ✅ General SKILL.md content structure (process, template, examples)
- ✅ Description requirements (third person, "Use when..." triggers)
- ✅ When to add scripts / when to split files
- ✅ Review checklist
- ✅ Quality standards (concrete examples, no time-sensitive info, consistent terminology)
