# Dev.md

## Working here

`bootstrap/targets/` declares hosts; `bootstrap/capabilities/` holds shared configuration and source assets. Agent plugins live in `agents/`, harness configuration in `bootstrap/capabilities/agent-harness/`, human documentation in `docs/`, and task entry points in `scripts/`.

Every host reconciles the same way:

```sh
mise <host>          # laptop | udmp | pod042 | omarchy | windows
mise <host> --check  # dry run
mise laptop -t shell # focused native capability
```

Gotcha: running this WILL change the host that the agent itself is running in, so be aware of what changes will actually apply.

On pod153 and pod042, a daily reconcile pulls main into the shared checkout and deploys it, including any uncommitted work in progress there.

On the work machine, the Artifactory mirror masks lockfiles with `skip-worktree`, so read [README.work.md](README.work.md) before pulling, rebasing, or bumping a dependency there.

Verification:

```sh
mise run check # every non-mutating check
mise run fix   # every formatter and autofixer
mise tasks     # the full list; --all adds the Go subproject
```

### Code style

- Host values belong in target configuration; shared declarations belong in the capability, not inline in task dispatchers.
- in the terminal, I use `cmd` to represent ghostty actions, `ctrl` for shell interactions, and `alt` for whatever is holding the alt-screen. This may not always be universally possible, but is a general rule of thumb

### Capabilities

A capability is a `mise.<capability>.toml` under `bootstrap/targets/<host>/`, selected through `MISE_ENV` in the order its host's reconcile driver lists. The target's `mise.toml` holds settings and resources shared by several capabilities.

- Keep resource ownership disjoint: mise merges the selected environments and gives a collision to the last one.
- Any subset of capabilities can be selected, so hooks must not branch on `MISE_ENV`.
- Don't name a capability after an operating system; mise selects those environments on its own.
- Prefer `[dotfiles]` for home configuration: symlink in-repo sources so application edits reach the repo, copy external Git sources, and render templates; accept source-derived permissions for ordinary files, and reserve `[bootstrap.files]` for secrets requiring private permissions, system files, explicit removals, or consumer-required permissions and ownership.
- Deleting a file from the repo does not remove it from a host. Declare a `state = "absent"` resource in the capability that owns the path, apply it on every affected host, then delete the declaration.

### Secrets

`fnox.toml` declares shared `op://` references and `fnox.<host>.toml` host-only ones; read one with `scripts/fnox-host get NAME`. This file is just a sublist of what is available from 1Password's `agent` vault, and when new needs arise you can add more secrets to the file.

## Beyond the hosts

- **Agent harnesses**: read [the agent-harness README](bootstrap/capabilities/agent-harness/README.md) before changing harness configuration, plugins, or models.
- **Cloudflare**: Terraform owns anything with a lifecycle at `terraform/cloudflare/`; Wrangler owns deployable code at `wrangler/` and `cloudflare-pages/`.
- **Google Cloud**: [terraform/google/](terraform/google/README.md).
- **Tailscale**: [terraform/tailscale/](terraform/tailscale/README.md). Edit the tailnet policy there, not in the admin console.
