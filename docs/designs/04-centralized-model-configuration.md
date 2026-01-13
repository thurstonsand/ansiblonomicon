# Centralized Model Configuration

## Problem Statement

Model versions and identifiers are duplicated across multiple files:

- `chezmoi/.chezmoitemplates/llm-models` (Go template with hardcoded values)
- `ansible/stacks/cli-proxy-api/.../config.yaml.j2` (Jinja2 with hardcoded values)
- `chezmoi/dot_config/zed/settings.json.tmpl`
- `chezmoi/dot_config/opencode/opencode.jsonc.tmpl`
- Various VS Code/Cursor/Windsurf settings templates

When model versions change (e.g., `claude-sonnet-4-5-20250929` → new dated release), updates must be made in multiple places.

Additionally, the agent harness needs model alias mappings for transforming Claude Code agent definitions to OpenCode format (e.g., `model: haiku` → `model: "anthropic/claude-haiku-4-5-20251001"`).

## Solution

Create a single YAML file (`ansible/models.yml`) as the source of truth, shared between:

- **Ansible** (via `include_vars`)
- **Chezmoi** (via symlink to `.chezmoidata/models.yaml`)

### Data Structure

```yaml
# ansible/models.yml
anthropic:
  sonnet:
    version: "claude-sonnet-4-5-20250929" # Dated version
    display_name: "Claude Sonnet 4.5"
    thinking: true
    max_input: 200000
    max_output: 64000
    vision: true
    names:
      claude: "sonnet" # Claude Code alias
      opencode: "anthropic/claude-sonnet-4-5-20250929" # OpenCode format
      zed: "claude-sonnet-4-5-latest" # Zed format
    cli_proxy_pattern: "^claude-sonnet-4-5" # Regex for CLI proxy normalization
```

### Access Patterns

**Chezmoi templates** (Go template syntax):

```go
{{- $m := .Data.models -}}
{{ $m.anthropic.sonnet.version }}
{{ $m.openai.gpt52.variants.high.id }}
```

**Ansible templates** (Jinja2 syntax):

```jinja2
{{ anthropic.sonnet.version }}
{{ anthropic.sonnet.cli_proxy_pattern }}
```

**Agent harness** (for model alias translation):

```jinja2
{{ anthropic.haiku.names.opencode }}
```

## Implementation Status

### Phase 1: Migrate Existing Model Usage ✅

| Task                                                    | Status     | Notes                                              |
| ------------------------------------------------------- | ---------- | -------------------------------------------------- |
| Create `ansible/models.yml`                             | ✅ Done    | New file with all model definitions                |
| Create `chezmoi/.chezmoidata/` directory                | ✅ Done    |                                                    |
| Symlink `models.yaml → ansible/models.yml`              | ✅ Done    |                                                    |
| Delete `chezmoi/.chezmoitemplates/llm-models`           | ✅ Done    | No longer needed                                   |
| Update CLI proxy config                                 | ✅ Done    | Uses `{{ anthropic.sonnet.version }}` etc.         |
| Update `zed/settings.json.tmpl`                         | ✅ Done    | Uses `$m := .Data.models`                          |
| Update VS Code settings templates                       | ✅ Done    | Code, Cursor, Windsurf, Code-Insiders, Antigravity |
| Update `opencode/opencode.jsonc.tmpl`                   | ✅ Done    |                                                    |
| Update `io.datasette.llm/extra-openai-models.yaml.tmpl` | ✅ Done    |                                                    |
| Update Ansible playbooks                                | ✅ Done    | Added `include_vars: models.yml`                   |
| Test `chezmoi apply`                                    | ❓ Pending | Verify templates render correctly                  |
| Test Ansible playbook                                   | ❓ Pending | Verify CLI proxy config generates                  |

### Phase 2: Agent Harness Model Mapping ✅

| Task                                  | Status  | Notes                                                              |
| ------------------------------------- | ------- | ------------------------------------------------------------------ |
| Add filter to translate model aliases | ✅ Done | `agent_harness_transform_skill` filter using `python-frontmatter`  |
| Update agent transformation logic     | ✅ Done | Applied in `deploy_single_skill.yml` and `deploy_single_agent.yml` |
| Test with sample agents               | ✅ Done | Unit tests in `test_harness_filters.py`                            |

## Files Changed

### New Files

- `ansible/models.yml` - Single source of truth
- `chezmoi/.chezmoidata/models.yaml` - Symlink to above

### Deleted Files

- `chezmoi/.chezmoitemplates/llm-models` - Replaced by shared data

### Modified Files

- `ansible/playbooks/local.yml` - Added `include_vars`
- `ansible/playbooks/truenas.yml` - Added `include_vars`
- `ansible/stacks/cli-proxy-api/.../config.yaml.j2` - Uses shared model data
- `chezmoi/dot_config/zed/settings.json.tmpl`
- `chezmoi/dot_config/opencode/opencode.jsonc.tmpl`
- `chezmoi/.chezmoitemplates/vscode-settings`
- `chezmoi/private_Library/.../Code/User/settings.json.tmpl`
- `chezmoi/private_Library/.../Cursor/User/settings.json.tmpl`
- `chezmoi/private_Library/.../Windsurf/User/settings.json.tmpl`
- `chezmoi/private_Library/.../Code - Insiders/User/settings.json.tmpl`
- `chezmoi/private_Library/.../Antigravity/User/settings.json.tmpl`
- `chezmoi/private_Library/.../io.datasette.llm/extra-openai-models.yaml.tmpl`

## Testing

### Chezmoi

```bash
chezmoi diff  # Preview what would change
chezmoi apply --dry-run  # Dry run
chezmoi apply  # Apply changes
```

### Ansible (CLI Proxy)

```bash
uv run poe truenas --tags docker-stack-role -c  # Dry run
uv run poe truenas --tags cli-proxy-api  # Apply
```

## Future Considerations

- The `names` field in each model enables Phase 2 agent harness work
- Adding new models requires updating only `ansible/models.yml`
- OAuth model mappings and excluded models also live in `models.yml`
