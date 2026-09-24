# Dev.md

## Setup

```sh
./scripts/bootstrap.sh                  # new Mac: Xcode CLI, Homebrew, mise, fnox, uv, 1Password CLI
```

`mise trust` does the rest — `uv sync --dev`, venv activation, `SUDO_ASKPASS`, the commit hook, Pi extension deps. The shared askpass helper is `scripts/sudo-askpass.sh`. Consumers resolve only their required credentials through fnox; laptop reconciliation has no enclosing fnox invocation.

## Working here

`bootstrap/targets/` declares hosts; `bootstrap/capabilities/` holds shared configuration and source assets. Agent plugins live in `agents/`, harness configuration in `bootstrap/capabilities/agent-harness/`, human documentation in `docs/`, and task entry points in `scripts/`.

Every host reconciles the same way:

```sh
mise <host>                # laptop | udmp | pod042
mise <host> --check        # dry run
mise laptop -t shell       # focused native capability
mise reconcile             # whichever of those this machine's hostname selects
mise run reconcile:tags    # this host's native tags
```

Gotcha: running this WILL change the host that the agent itself is running in, so be aware of what changes will actually apply.

Verification:

```sh
mise run check             # every non-mutating check
mise run fix               # every formatter and autofixer
mise run python:lint       # or nvim:fmt:check, workers:typecheck,
                           # pi:check, amp:check, session-recovery:check
mise tasks                 # the full list; --all adds the two Go subprojects
uv run pytest
```

### Code style

- Prefer extending the capability that owns the resource over adding one.
- Host values belong in target configuration; shared declarations belong in the capability, not inline in task dispatchers.

### Native bootstrap capabilities

A capability lives in `bootstrap/targets/<host>/mise.<capability>.toml`; the target's `mise.toml` holds settings and resources shared by multiple capabilities. Register capability order in both the host driver and `bootstrap/mise.toml`. Keep resource ownership disjoint across capability files because mise environments resolve collisions last-wins, reserve mise's OS environment names, and keep hooks independent of `MISE_ENV`. Retire managed files and directories with native `state = "absent"` declarations.

Prefer `[dotfiles]` for home configuration: symlink in-repo sources so application edits reach the repo, copy external Git sources, and render templates; accept source-derived permissions for ordinary files, and reserve `[bootstrap.files]` for secrets requiring private permissions, system files, explicit removals, or consumer-required permissions and ownership.

### Secrets

Declare shared `op://` references in `fnox.toml` and host-only references in `fnox.<host>.toml`. Read one with `scripts/fnox-host get NAME`.

### Retiring managed state

Deleting a file from the repo does not remove it from a host. Declare a `state = "absent"` resource in the capability that owns the path, apply it on every affected host, then delete the declaration.

## macOS

Hostname selects the native target. Both laptops reject unknown tags before taking action. Work's private inputs live in ignored files under its target, the agent-harness `local/` directory, and `mise.work-local.local.toml`, applied by the `work-local` capability; see [README.work.md](README.work.md).

```sh
mise laptop -t homebrew    # also: language-tools, shell, agent-harness
```

Homebrew formulae, casks, and Mac App Store apps come from `bootstrap/capabilities/mac-apps/Brewfile`, with `Brewfile.work` for work. `Brewfile.work` includes any ignored `Brewfile.work.*` beside it. Go and UVC sources live under `bootstrap/capabilities/software/sources/`. System preferences and sudo Touch ID live in `bootstrap/capabilities/macos-system`, grouped by domain for `mise laptop -t dock,finder` or reconciled together with `mise sysconfig`.

The work mirror rewrites lockfile URLs, so `uv.lock` and some `package-lock.json` files are masked with `skip-worktree` there. Use `mise run pull`, and be careful with `merge`, `rebase`, or `stash pop` on work. Confirm a version exists on the mirror before bumping a dependency.

## pod042

The physical Debian NAS, declared in `bootstrap/targets/pod042/`.

## UDMP

The home router.

```sh
mise udmp                  # OS services through native mise remote bootstrap
mise udmp --check          # preview OS changes
mise udmp --update-mise    # refresh the system-wide remote mise executable
mise run unifi:init        # install the verified provider fork and initialize OpenTofu
mise run unifi:plan        # Network application resources
mise run unifi:apply
mise run unifi:smoke       # read-only WAN, LCT, DNS, link, and mDNS checks
```

Remote inventory in `bootstrap/mise.toml`. Resources in `terraform/unifi/`.

## Agent tooling

Spans every host and every harness. `bootstrap/capabilities/agent-harness/` is canonical: `catalogue.toml`, `profiles.toml`, and `harnesses/` declare plugins; `harness_filters.py` owns resolution; `configuration/data.toml`, `configuration/templates/`, and `configuration/assets/` declare settings and source assets. Host-local, untracked configuration overlays belong in `bootstrap/capabilities/agent-harness/local/<hostname>/data.toml`. Host-local plugin sources belong in `local/<hostname>/catalogue.toml` beside it. Native `agent-config` owns settings and assets on every registered host.

- **Plugins** at `agents/<plugin>/skills/`, listed in `.claude-plugin/marketplace.json`. A skill may be a plain `SKILL.md` or a `SKILL.md.j2` templated at deploy time, and this applies to any other `.j2` file in the skill dir. Repo-local skills live at `.agents/skills/`, symlinked into `.claude/skills/`. The `.j2` skills mean a plugin is not installable through Claude's own plugin mechanism, which does no templating — deployment goes through `agent_harness` instead. see `agents/README.md` for more.
- **User-level instructions** render from `configuration/templates/`; Amp's hosted instructions remain updated by hand.
- **Models** at `bootstrap/capabilities/agent-harness/models.yml` are the single source for versions, aliases, and per-editor config. Native renderers merge them with `configuration/data.toml` and the host overlay.
- **Assets** under `configuration/assets/` are first-party source. `assets.toml` declares assets, package dependencies, and explicit retirements; native configuration symlinks unchanged files into `$HOME` and renders host-dependent or secret-bearing files as regular files. Never put credentials in templates, assets, or host overlays: declare SecretRefs in fnox and let `agent-config` resolve only the keys required by that host. Private outputs use mode `0600`.
- **Amp User Skills** are rendered natively by `publish_amp_skills.py` using the `amp_publish` profile. `scripts/publish-amp-skills.sh` is the CI entry point, triggered on relevant main-branch pushes and a daily schedule. Overrideable by explicitly specifying `amp` as a target of a skill.
- **Session recovery** lives under `configuration/assets/shared/session-recovery/`, with consumers under the Pi and Claude asset trees. Lint it through `mise run session-recovery:check` rather than from inside a consumer.

Run `mise agent-config --check` for a placeholder-secret preview; exit 2 means the preview completed but secret-backed content remains unresolved. Use `mise agent-config --check --real-secrets` for read-only parity with resolved credentials, and `mise agent-config` to apply. `mise agent-harness` runs the catalogue first and then configuration; full host reconciliation routes both through the `agent-harness` tag.

## Cloudflare

Split by tool, not by resource. Terraform owns anything with lifecycle — DNS, tunnels, Zero Trust, R2, rulesets, zone settings — at `terraform/cloudflare/`, applied with OpenTofu. Wrangler owns deployable code: Workers at `wrangler/{aig,hooks}/` and Pages sites at `cloudflare-pages/`.

```sh
mise run edge:plan         # plan; edge:init and edge:apply for init and apply
mise run edge:deploy       # both Workers; edge:deploy:aig and :hooks individually
mise run edge:deploy:tesla
```

Worker deploys manage their own secrets through the deploy scripts; pass `--force-secret` to overwrite existing ones.
