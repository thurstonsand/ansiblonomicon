---
name: librarian
description: Spin up isolated sandbox containers with OpenCode to work on git repos. Containers persist for follow-up questions in the same session.
metadata: {"clawdbot":{"emoji":"📚","requires":{"bins":["docker"]}}}
---

# Librarian - Sandboxed Coding Agent

Spawn isolated Docker containers with OpenCode to work on any git repository. Each sandbox persists for the session, allowing follow-up questions and iterative work.

## Quick Start

```bash
# Spawn a sandbox for a repo
librarian spawn --repo https://github.com/user/repo --task "Add unit tests for the auth module"

# Follow up in the same sandbox
librarian ask --session abc123 "Now run the tests and fix any failures"

# Check status
librarian status --session abc123

# Get logs
librarian logs --session abc123

# Clean up when done
librarian kill --session abc123
```

## Commands

### spawn - Create a new sandbox

```bash
librarian spawn \
  --repo <git-url>           # Required: repo to clone
  --task "<instructions>"    # Required: what OpenCode should do
  --branch <branch>          # Optional: branch to checkout (default: main/master)
  --session <id>             # Optional: custom session ID (auto-generated if omitted)
  --model <model>            # Optional: model for OpenCode (default: claude-sonnet-4-20250514)
```

**Example:**
```bash
librarian spawn \
  --repo https://github.com/fastapi/fastapi \
  --task "Review the dependency injection system and suggest improvements" \
  --branch main
```

### ask - Send follow-up to existing sandbox

```bash
librarian ask --session <id> "<follow-up question or task>"
```

**Example:**
```bash
librarian ask --session abc123 "Based on your review, implement the top 3 improvements"
```

### status - Check sandbox state

```bash
librarian status --session <id>
# Returns: running, idle, exited, not_found
```

### logs - Get OpenCode output

```bash
librarian logs --session <id>
librarian logs --session <id> --tail 100  # Last 100 lines
librarian logs --session <id> --follow    # Stream live
```

### list - Show all active sandboxes

```bash
librarian list
# Shows: session_id, repo, status, created_at, last_activity
```

### kill - Destroy a sandbox

```bash
librarian kill --session <id>
librarian kill --all  # Kill all sandboxes (cleanup)
```

## How It Works

1. **spawn** creates a Docker container with:
   - OpenCode pre-installed
   - Git, common dev tools
   - The specified repo cloned to `/workspace`
   - A tmux session for persistent interaction

2. **OpenCode runs** with your task instructions in the cloned repo

3. **Session persists** - container stays running until killed

4. **ask** sends new prompts to the same OpenCode instance via tmux

5. **Artifacts persist** - changes, commits, files all remain in the container

## Session Persistence

Sandboxes are identified by session ID (auto-generated or custom). The container naming convention is:

```
clawdbot_librarian_<session_id>
```

Sessions survive:
- Network interruptions
- Gateway restarts (containers are independent)
- Multiple follow-up questions

Sessions are destroyed by:
- Explicit `librarian kill`
- Container crash/OOM
- Host reboot

## Environment Variables (in sandbox)

| Variable | Value |
|----------|-------|
| `WORKSPACE` | `/workspace` (repo root) |
| `ANTHROPIC_API_KEY` | Inherited from gateway |
| `OPENAI_API_KEY` | Inherited from gateway (if set) |
| `GITHUB_TOKEN` | Inherited from gateway (if set) |

## Tips

### Long-running tasks
For tasks that take a while, spawn and check back:
```bash
librarian spawn --repo ... --task "Refactor entire codebase to TypeScript"
# ... do other things ...
librarian logs --session abc123 --tail 50
```

### Multiple sandboxes
Run parallel investigations:
```bash
librarian spawn --repo https://github.com/org/frontend --task "Audit for XSS vulnerabilities" --session audit-fe
librarian spawn --repo https://github.com/org/backend --task "Audit for SQL injection" --session audit-be
librarian list
```

### Commit results
Ask OpenCode to commit:
```bash
librarian ask --session abc123 "Commit your changes with a descriptive message"
```

### Push results (requires auth)
For pushing, either:
1. Use a repo you have SSH access to
2. Set `GITHUB_TOKEN` in the gateway environment

```bash
librarian ask --session abc123 "Push your changes to a new branch called feature/improvements"
```

## Limitations

- **No GUI**: Sandboxes are headless
- **No network isolation**: Containers can access the network (for package installs, API calls)
- **Resource limits**: Default 2GB RAM, 2 CPU cores per sandbox
- **Ephemeral storage**: Container filesystem is lost on kill (commit/push important changes!)

## Implementation Notes

The skill uses:
- Docker API via mounted socket
- OpenCode in headless/print mode for non-interactive runs
- tmux for session persistence and follow-up interaction
- Named containers for session tracking

Container lifecycle:
```
spawn → running (opencode working) → idle (waiting for ask) → kill → removed
```
