# User tools capability

Native mise owns the remaining shared CLI configuration and standalone helpers: LazyGit, SourceKit-LSP, Vim, markdownlint, a terminal-title helper, plus stable links to the repository's `fnox-host` and MCP credential launchers. Personal hosts additionally receive GitHub CLI and Rustup configuration; work intentionally receives neither.

It also links small desktop application files to their sources. Every laptop receives Go's local-only telemetry mode: `mise.mac.toml` places it for both Macs, and the Omarchy target owns its Linux path. `mise.mac-personal.toml` gives the personal Mac LinearMouse, NextDNS, mactop, and herdr endpoints; the Omarchy target declares its own herdr endpoints. The NextDNS file is configuration text only: this capability does not activate DNS or update its addresses.

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
