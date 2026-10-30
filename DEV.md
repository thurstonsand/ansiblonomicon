# Dev.md

## Setup

```sh
./scripts/bootstrap.sh                  # new Mac: Xcode CLI, Homebrew, mise, fnox, uv, 1Password CLI
```

`mise trust` activates the venv and installs the commit hook on shell entry. The shared askpass helper is `scripts/sudo-askpass.sh`: it resolves the host's sudo password through fnox, so reconciliation tasks gain root without anyone at the keyboard. The work Mac's BeyondTrust sudo keeps no timestamp for a `sudo -A -v` to prime. On the Omarchy laptops, `sudo -A` authenticates through the password-only `sudo-unattended` PAM service instead of waiting on the fingerprint or security key that plain `sudo` asks for, and each use raises a desktop notification. Consumers resolve only their required credentials through fnox.

## Working here

`bootstrap/targets/` declares hosts; `bootstrap/capabilities/` holds shared configuration and source assets. Agent plugins live in `agents/`, harness configuration in `bootstrap/capabilities/agent-harness/`, human documentation in `docs/`, and task entry points in `scripts/`.

Every host reconciles the same way:

```sh
mise <host>                # laptop | udmp | pod042 | omarchy | windows
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
mise run python:lint       # or nvim:fmt:check, workers:typecheck, pi:check
mise tasks                 # the full list; --all adds the Go subproject
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

Hostname selects the native target: `pod153` or the work Mac. Both reject unknown tags before taking action. Work's private inputs live in ignored files under its target, the agent-harness `local/` directory, and `mise.work-local.local.toml`, applied by the `work-local` capability; see [README.work.md](README.work.md).

```sh
mise laptop -t homebrew    # also: language-tools, shell, agent-harness
```

Homebrew formulae, casks, and Mac App Store apps come from `bootstrap/capabilities/mac-apps/Brewfile.pod153`, with `Brewfile.work` for work; `Brewfile` keeps the desktop loadout pod153 ran before it became a server. `Brewfile.work` includes any ignored `Brewfile.work.*` beside it. Go and UVC sources live under `bootstrap/capabilities/software/sources/`. System preferences and sudo authentication live in `bootstrap/capabilities/macos-system`, grouped by domain for `mise laptop -t dock,finder` or reconciled together with `mise sysconfig`.

The work mirror rewrites lockfile URLs, so `uv.lock` and some `package-lock.json` files are masked with `skip-worktree` there. Use `mise run pull`, and be careful with `merge`, `rebase`, or `stash pop` on work. Confirm a version exists on the mirror before bumping a dependency.

## pod042

The physical Debian NAS, declared in `bootstrap/targets/pod042/`. The `dev.mise.reconcile-daily.timer` user timer runs `scripts/reconcile-or-fix` at 05:30, an hour after pod153's, so the two never push to main at once; `remote-development` declares it. On both hosts the script commits and pushes the `lazy-lock.json` that the plugin sync rewrites. Other agents share the checkout, so the pull autostashes their uncommitted work and the reconcile deploys it along with main; only incoming commits that conflict with that work stop the run before the rebase. A failure goes to an agent, which sets unfinished work that caused it aside, reconciles main, and puts the work back in progress.

## pod153

The MacBook Pro, run as an always-on headless server and reconciled by `mise laptop`. Its `server` capability keeps it awake with the lid closed, reachable over Remote Login and Screen Sharing, and runs Cua Driver, Claude Remote Control, ChatGPT, and a daily 04:30 `scripts/reconcile-or-fix` as LaunchAgents. That script pulls main and reconciles; on failure it starts an Amp thread on pod153's own runner that fixes and pushes, or notifies Thurston when the fix needs him. Nothing unattended may depend on the 1Password app or its SSH agent. pod042's `dev.mise.pod153-wake` service unlocks FileVault over pre-boot SSH after an unplanned restart. `agents/homelab/skills/operating-pod153/` covers boot states, restarts, and answering macOS prompts.

## Omarchy laptops

`type-a-no2` and `no9-type-s` are the personal laptops running Omarchy, each reconciled by `mise omarchy`; `-t omarchy-config` and friends narrow it like the laptop tags. Any customization on these laptops should build on top of and integrate with the native Omarchy methodology and style. Ideally, everything should be done Omarchy-native, then captured in the repo as is relevant. Both targets symlink the shared `bootstrap/capabilities/omarchy/` capability, and each adds what only it has in `mise.omarchy-host.toml` and `omarchy-host/`: monitors and the bar everywhere, plus the YubiKey lock and eGPU on `type-a-no2`. The `omarchy-loadout` capability reads packages, themes, and plugins from the shared `bootstrap/capabilities/omarchy/loadout.toml`, adds the host's own `loadout.toml` when it has one, and reconciles them in a way native to Omarchy. A declaration lives in exactly one of the two. Declare a theme or plugin by its Omarchy name or id with its git `source`, and mark a retired entry `absent` to remove it explicitly, then delete the line once applied. Upgrades are natively managed by `omarchy update`, `omarchy theme update`, `omarchy plugin update`, and `mise upgrade` for the global mise tools; `mise omarchy --full` runs them unattended.

Optional theme or plugin extras, such as `theme-set` hooks or files an author asks you to copy into another app, are ordinary `[dotfiles]` in `mise.omarchy-config.toml`, which runs after installs. Keep repo-owned extras under `bootstrap/capabilities/omarchy/files/themes/<name>/`; a file copied from the install itself can use its `~/.config/omarchy/themes/<name>/` path as the source. Web apps follow the same rule: create one with `omarchy-webapp-install`, then move its `.desktop` file and icon under the capability's `files/applications/` and `files/icons/`, or under `omarchy-host/` for one laptop, and symlink them back.

Software missing from Omarchy's repositories uses its vendor's installer instead of the AUR.

`omarchy-config` declares the NetworkManager Wi-Fi profiles as templated keyfiles with fnox passphrases, so a reconcile reverts changes made through `nmcli` or the network panel.

## Windows

`eve` is the Framework laptop's Windows side, dual-booting with Omarchy, reconciled natively by `mise windows`; `-t windows-system` and friends narrow it. Tasks run under Git Bash, selected by the global mise config the `mise` tag links, so the target never assumes WSL. `windows-apps` declares winget packages in `[bootstrap.packages]`, and `windows-system` owns the registry values in the target's `windows-system.toml`, asking UAC once when a machine-wide value differs. `vcs` turns off Git for Windows' CRLF conversion and turns on symlinks. `amp-cli` runs the Amp runner as the `mise\amp-runner` Scheduled Task at logon, windowless under a headless conhost, with `amp-runner.ps1` restarting it and taking it down with the task.

A fresh Windows host needs Git for Windows and Developer Mode first, because the repo and its dotfiles are symlinks. Then:

```powershell
git clone -c core.symlinks=true -c core.autocrlf=false git@github.com:thurstonsand/ansiblonomicon.git
cd ansiblonomicon
irm https://mise.run/powershell | iex      # official build at ~\.local\bin, so self-update works
mise -C bootstrap/targets/eve bootstrap --only dotfiles --force-dotfiles --yes
mise trust; mise run bootstrap; mise windows
mise --no-env exec -- python3 scripts/automation_identity.py
```

The identity is the laptops' shared automation token, kept readable only by its owner through the file's access list instead of mode 0600.

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
- **User-level instructions** live in `instructions/AGENTS.md.tera`; `mise run amp:guidance` renders Amp's `global_agent_guidance`.
- **Models** at `bootstrap/capabilities/agent-harness/models.yml` are the single source for versions, aliases, and per-editor config. Native renderers merge them with `configuration/data.toml` and the host overlay. Haiku's small jobs, such as Pi's and Claude Code's session titles and Pi's working vibes, call Anthropic's API directly with the metered `ANTHROPIC_API_KEY`, not a subscription login; filter platform.claude.com's Usage and Cost pages by that key to see their spend.
- **Assets** under `configuration/assets/` are first-party source. `assets.toml` declares assets, package dependencies, and explicit retirements; an asset naming a `harness` deploys only where `profiles.toml` targets it, and `hosts` narrows host-specific content; native configuration symlinks unchanged files into `$HOME` and renders host-dependent or secret-bearing files as regular files. Never put credentials in templates, assets, or host overlays: declare SecretRefs in fnox and let `agent-config` resolve only the keys required by that host. Private outputs use mode `0600`.
- **Amp User Skills** are rendered natively by `publish_amp_skills.py` using the `amp_publish` profile. `scripts/publish-amp-skills.sh` is the CI entry point, triggered on relevant main-branch pushes and a daily schedule. Overrideable by explicitly specifying `amp` as a target of a skill.
- **Amp Tune Modes pins** for the built-in modes are declared in the `amp` block of `models.yml`; Amp's factory dial and automatic routing cover everything else. Amp has no supported CI settings writer, so apply `mise run amp:modes` through `manage_amp`; the publish workflow fails when the live pins or dial drift.

Run `mise agent-config --check` to preview and `mise agent-config` to apply. `mise agent-harness` runs the catalogue first and then configuration; full host reconciliation routes both through the `agent-harness` tag.

## Cloudflare

Split by tool, not by resource. Terraform owns anything with lifecycle — DNS, tunnels, Zero Trust, R2, rulesets, zone settings — at `terraform/cloudflare/`, applied with OpenTofu. Wrangler owns deployable code: Workers at `wrangler/{aig,hooks}/` and Pages sites at `cloudflare-pages/`.

```sh
mise run edge:plan         # plan; edge:init and edge:apply for init and apply
mise run edge:deploy       # both Workers; edge:deploy:aig and :hooks individually
mise run edge:deploy:tesla
```

Worker deploys manage their own secrets through the deploy scripts; pass `--force-secret` to overwrite existing ones.

## Google Cloud

`terraform/google/` holds every Google Cloud project I keep, one file per project: `cloudflare` (the Access SSO OAuth client), `gemini` (the AI Studio project and its Gemini auth key), `inbox_zero` (Inbox Zero's OAuth client and its Gmail push topic), and `nest` (the Device Access project's OAuth client and its `nest-events` topic). It authenticates with my user's application default credentials from `gcloud auth login --update-adc`. The Device Access Console, OAuth consent screens, and OAuth clients have no usable API, so they stay manual.

```sh
mise run google:plan       # google:init and google:apply for init and apply
```

## Tailscale

`terraform/tailscale/` owns the tailnet: the policy file in `policy.hujson`, DNS, tailnet settings, contacts, the `amp-orb` OAuth client, and the key expiry and subnet routes of the unattended machines. Edit the policy there, not in the admin console. It authenticates with the all-scope OAuth client in 1Password, which stays unmanaged so an apply can never revoke its own credential. Auth keys, API tokens, and personal devices stay out, since their owners rotate them. Each host's own tags and Tailscale SSH come from its `tailscale up` in the host reconcile.

```sh
mise run tailscale:plan    # tailscale:init and tailscale:apply for init and apply
```
