# User tools capability

Native mise owns the remaining shared CLI configuration and standalone helpers: LazyGit, SourceKit-LSP, Vim, markdownlint, terminal-title and Hunk editor helpers, plus stable links to the repository's `fnox-host` and MCP credential launchers. Personal hosts additionally receive GitHub CLI and Rustup configuration; work intentionally receives neither.

Run `mise user-tools` or `mise user-tools --check` on a registered host. LazyGit discovers Hunk first and Delta second while rendering. Its optional `vars.lazygit_services` is trusted native LazyGit YAML and defaults to an empty string. When configured, the value must be the indented body of the `services` mapping. Preserve the two-space indentation inside the TOML multiline literal exactly:

```toml
[vars]
lazygit_services = '''
  "gitlab.example.com": "gitlab:gitlab.example.com"
  "stash.example.com:7999/projects/tools": "bitbucketServer:stash.example.com:7999/projects/tools"
'''
```

The template emits `services:` only when this value is nonempty, then inserts the trusted YAML body unchanged.

The GitHub CLI and Rustup files are copied/rendered rather than linked back to the checkout because those tools may update their configuration. All other static files and helpers remain links to their authoritative sources.
