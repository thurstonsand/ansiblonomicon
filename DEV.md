# Dev.md

## Setup

```sh
./scripts/bootstrap.sh                  # new machine: Xcode CLI, Homebrew, Ansible, chezmoi, 1Password CLI
./scripts/bootstrap.sh --ignore-certs   # behind a TLS-intercepting proxy
```

`direnv allow` does the rest — `uv sync --dev`, venv activation, `ANSIBLE_CONFIG` and `SUDO_ASKPASS`, pre-commit install, Pi extension deps, and secret resolution. Sudo is answered from 1Password; no manual password entry.

## Working here

`ansible/` declares what a host should have. `chezmoi/` holds what lands in `$HOME`, delivered by the `chezmoi` role during reconciliation. Anything an agent consumes lives in `agents/`, anything I read lives in `docs/`, and `scripts/` holds what Poe shells out to.

Every host reconciles the same way:

```sh
uv run poe <host>          # laptop | truenas | udmp | pod042
uv run poe <host> --check  # dry run
uv run poe <host> -t chezmoi
uv run poe list-tags       # what this machine's playbook offers; takes an optional playbook name
```

Gotcha: running this WILL change the host that the agent itself is running in, so be aware of what changes will actually apply.

Verification:

```sh
uv run poe lint            # everything
uv run poe lint:{ansible,python,nvim,workers,pi,session-recovery,amp,cli-tools}
uv run poe lint:pi -f      # -f applies formatting first, on any TypeScript subtask
uv run pytest
```

### Code style

- Prefer extending a role over adding one.
- Facts belong in `config.yml` or `<host>.config.yml`, not usually inline in a task.

### Secrets

Add an `op://` SecretRef to `.secrets.jsonc`, then `uv run poe init-secrets`. Consumers read it three ways: Ansible through `lookup('env', 'NAME')`, Terraform through a `TF_VAR_*` variable, chezmoi through an `op-secret` wrapper template in `.chezmoitemplates/`.

### Retiring managed state

Deleting a file from the repo does not remove it from a host. Declare the retirement instead: `.ansibleremove` for Ansible-managed paths, consumed by the macOS and pod042 playbooks; `.chezmoiremove` for dotfiles, consumed wherever chezmoi applies. TrueNAS and UDMP require manual cleanup.

## macOS

One playbook per machine, selected by hostname. `macos.yml` layers `darwin.config.yml` over the shared config; `work.yml` takes `work.config.yml` instead, plus an untracked `work.config.local.yml` for anything that cannot be committed.

```sh
uv run poe laptop -t homebrew          # also: chezmoi, language-tools
```

Homebrew formulae, casks, and Mac App Store apps come from `ansible/Brewfile`, with `Brewfile.work` for the work machine. System preferences live in the `macos_defaults` role, grouped by domain so they can be applied piecemeal.

The work mirror rewrites lockfile URLs, so `uv.lock` and some `package-lock.json` files are masked with `skip-worktree` there. Use `uv run poe pull`, and be careful with `merge`, `rebase`, or `stash pop` on work. Confirm a version exists on the mirror before bumping a dependency.

## pod042

Reconciles itself: the playbook asserts a local connection and matching hostname, so there is no workstation-driven remote path.

```sh
ssh pod042 && cd ansiblonomicon && uv run poe pod042 -t chezmoi   # also: language-tools, nvim-deps
```

Config in `pod042.config.yml`, inventory in `inventory/targets/pod042.yml`. Packages come from apt with explicit external repos, plus mise and npm. Secrets arrive through a scoped 1Password service account installed by the `op_service_account` role. Docker work targets the NAS daemon over SSH rather than a local one, automatically configured.

## TrueNAS

One playbook, two declaration sites: stacks are templated under `ansible/stacks/` and rendered by the `docker_stack` role; everything else — apps, and all of `local.truenas` — is declared in `inventory/targets/group_vars/truenas.yml`.

```sh
uv run poe list-tags truenas     # then reconcile just the stack you touched
uv run poe truenas -t <tag>
```

Compose files and container data live apart on disk — `/mnt/performance/docker/stacks/{stack}/compose.yaml` versus `/mnt/performance/docker/{stack}/{container}/config`. Host addresses, ports, domains, and the macvlan network tiers are all declared in `group_vars/truenas.yml` under `lan`; take values from there rather than hardcoding.

## UDMP

The home router.

```sh
uv run poe udmp -t nextdns            # or multicast-querier
```

## Agent tooling

Spans every host and every harness. Driven by `roles/agent_harness/vars/agents.yml` with sources in `agent-harness.config.yml` and host-specific configs in `agent_harness_profile`.

- **Plugins** at `agents/<plugin>/skills/`, listed in `.claude-plugin/marketplace.json`. A skill may be a plain `SKILL.md` or a `SKILL.md.j2` templated at deploy time. Repo-local skills live at `.agents/skills/`, symlinked into `.claude/skills/`. The `.j2` skills mean a plugin is not installable through Claude's own plugin mechanism, which does no templating — deployment goes through `agent_harness` instead. see `agents/README.md` for more.
- **User-level Instructions** at `chezmoi/.chezmoitemplates/agents-md`, rendered per harness into `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.pi/agent/AGENTS.md`, and the rest. The persona fragment it pulls in is `.chezmoitemplates/2b-persona`. This is not the same file as the repo's own `AGENTS.md`.
- **Models** at `ansible/models.yml` — the single source for versions, aliases, and per-editor config, symlinked to `chezmoi/.chezmoidata/models.yaml`. `ansible/session-title-prompt.txt` is symlinked the same way.
- **Pi** at `chezmoi/private_dot_pi/agent/`: extensions under `extensions/`, permission rules under `permissions/`, external packages referenced from `settings.json.tmpl`.
- **Amp** at `chezmoi/dot_config/amp/plugins/`.
- **Amp User Skills** are rendered from the Amp-targeted `agent_harness` sources and published after relevant changes reach `main` and once daily to pull upstream skill updates, making them available in every local thread and orb. The workflow requires the repository's `AMP_API_KEY` secret; preview its output with `scripts/publish-amp-skills.sh --dry-run`.
- **Codex** at `chezmoi/.chezmoitemplates/codex-config.toml.tmpl` — the declared keys only. Codex and the ChatGPT app write into the file as well, so it's additive.
- **Session recovery**: the shared core at `chezmoi/dot_local/lib/session-recovery/`, consumed by a Pi extension at `private_dot_pi/agent/extensions/session-recovery/` and a Claude script at `dot_claude/scripts/session-recovery/`. User config sits at `dot_config/session-recovery/`. Consumers carry no devDeps and borrow the core's toolchain, so lint it through `poe lint:session-recovery` rather than from inside a consumer.

## Cloudflare

Split by tool, not by resource. Terraform owns anything with lifecycle — DNS, tunnels, Zero Trust, R2, rulesets, zone settings — at `terraform/cloudflare/`, applied with OpenTofu. Wrangler owns deployable code: Workers at `wrangler/{aig,hooks}/` and Pages sites at `cloudflare-pages/`.

```sh
uv run poe tfp             # plan; tfi and tfa for init and apply
uv run poe wrangler        # both Workers; wrangler:aig and wrangler:hooks individually
uv run poe pages-deploy
```

Worker deploys manage their own secrets through the deploy scripts; pass `--force-secret` to overwrite existing ones.
