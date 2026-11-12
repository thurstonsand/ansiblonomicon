# Declarative agent harness capability

`catalogue.toml` is the single checked-in plugin catalogue. `harness_filters.py` beside it performs manifest discovery, selector handling, and the per-harness SKILL.md transforms; `models.yml` and `session-title-prompt.txt` are the canonical model catalogue and session-title prompt that those transforms, the configuration renderers, and skill templates read. Skill templates reach files in this directory through the `agent_harness_root` Jinja global. Templates also see `hostname`, `home`, and the `harness` they render for, and `lookup('file', path)` reads a file inside the checkout. A host's private plugin sources belong in the ignored `local/<hostname>/catalogue.toml`, a bare `[[sources]]` array appended to the shared catalogue.

A skill or agent's frontmatter `model:` names a `models.yml` tier, such as `fable`, and deploys as that tier's `agent_harness.aliases.<harness>`; a name with no alias for a target harness fails the deploy. An inline mapping selects a tier per harness, for example `model: {claude: fable, pi: gpt_astra}`. A host whose `local/<hostname>/data.toml` declares `work_models` resolves Pi through each tier's `pi_alias` there instead.

Each `harnesses/<name>/mise.toml` is a native mise project fragment. Its `[harness]` table declares destination roots, the name transform, and whether the harness reads symlinked files; it may also compose ordinary `[vars]`, `[dotfiles]`, and `[bootstrap.files]` resources owned by that harness. Only fragments for harnesses the selected profile targets are applied. For example, a template stored beside the declaration can become a native dotfile:

```toml
[vars]
channel = "stable"

[dotfiles."~/.claude/settings.toml"]
source = "settings.toml.tera"
mode = "template"

[bootstrap.files."~/.claude/credentials"]
source = "credentials.tera"
template = true
mode = "0600"
```

`profiles.toml` is the single declaration of which harnesses a host targets: each profile lists its `target_agents` and `explicit_only` harnesses. The catalogue engine deploys skills and agents only to those harnesses, and native `agent-config` runs only their renderers (`configuration/<harness>.py`), instruction files, and `configuration/assets.toml` entries naming them. A native host declaration selects a profile, template hostname, source update policy, and ownership manifest. pod153's declaration is `bootstrap/targets/pod153/mise.agent-harness.toml`, the work Mac's is `bootstrap/targets/ML-DFC6YK6VJQ/mise.agent-harness.toml`, and pod042's is `bootstrap/targets/pod042/agent-harness/host.toml`; `configuration/deploy.py` maps each hostname to its declaration.

`agent-config` installs command-timing and comment guards for Pi, Claude Code, and Codex. Shell results gain elapsed-time feedback, a warning above 60 seconds, and a stronger warning above 5 minutes; required final validation still runs. Claude uses native execution duration when available; otherwise timing includes hook and approval wait, and detached launches measure the tool call rather than the background process. Codex requires review in `/hooks` before running newly installed hooks. Comment guards reject new full-line comments containing chat or edit-history phrases such as “as requested” and “changed from”, while allowing rationale comments and unchanged lines. This is a text heuristic, not a parser: inline comments and files written through shell commands are outside its coverage. Amp's equivalents are declared in `amp-plugins/` and published to the global User Plugins repository by CI, separately from host reconciliation.

Run the hook and publication checks with `uv run --no-sync python -m unittest discover -s bootstrap/capabilities/agent-harness/configuration/tests -v` and `node --test bootstrap/capabilities/agent-harness/configuration/tests/{pi,amp}-hooks.test.mjs`.

A plugin's MCP servers deploy as Claude Code installs them: the manifest's `mcpServers`, or the `.mcp.json` at its root, becomes a fragment under the harness cache, and each server is named `plugin_<plugin>_<server>` so the plugin's own skills, agents, and hook matchers find its tools. `mcp = false` on a catalogue row leaves them out, and `target_agents` narrows them like the plugin's other resources. `configuration/deploy.py` merges those servers with the host's `[[mcp_servers]]`, where an entry of the same name overrides the plugin's fields, and renders the result for Claude Code, Codex, and Pi. An entry's `harnesses` list narrows it, and `tool_timeout_sec` and `oauth = { client_id, callback_port }` reach each harness in its own form. Codex's `env_vars`, `omit_tools_from`, and `supports_parallel_tool_calls` require `harnesses = ["codex"]`.

`agent_harness_deploy.py` is the common deployment engine. It renders through `catalogue.py`, aggregates repeated selector rows by stable `source + plugin` identity, and records an exact per-plugin inventory. Omitting a previously deployed plugin is a no-op: all of its recorded paths and its source-plus-plugin provenance remain available for a later explicit retirement. Add that same identity with `remove = true` to retire it, including while its checkout is unavailable:

```toml
[[sources]]
repo = "owner/catalogue"

[[sources.plugins]]
name = "retired-plugin"
remove = true
```

Without inventory, removal must resolve the declaration or fail. Target and selector changes retire only paths owned by the affected plugin.

Native mise dotfiles deploy unchanged local-source files as symlinks to their repository source, except where the harness declares `symlink_local_files = false`. Files from Git checkouts are copies, while templates and harness-transformed files are real files backed by a durable rendered generation. Native absence resources remove stale exact files. Before using mise's force mode, the engine requires every existing destination to be recorded or byte/mode-equivalent to the desired deployment. Cleanup is exact-file ownership; there is no whole-directory prune.

The version 3 ownership manifest also retains a canonical, profile-resolved selector fingerprint per source-plus-plugin owner. An unchanged, previously successful declaration may lose an individually named include, exclude, or explicit-map path upstream; that resource is then retired by exact ownership. New or changed declarations remain strict, including explicit empty maps, and missing checkouts or manifests remain errors. The engine rejects any other manifest version as malformed.

The ownership manifest is atomically expanded before native apply and narrowed only after success. Selector proof is retained on empty tombstones, omitted owners, and pending recovery; old rendered bytes are never replayed. Destination parents may not redirect outside the operator home; intentional local-source links may point back into the repository. `--check` requires cached Git sources and writes neither source timestamps nor managed state. `--cached` applies the fixed cache. Normal updates are every 86400 seconds on the Mac and every run on pod042.

Run `mise agent-harness [--check|--cached]` on any registered system. pod042 retains its hostname, UID, GID, and home guard.

## Agent tooling

Spans every host and every harness. `bootstrap/capabilities/agent-harness/` is canonical: `catalogue.toml`, `profiles.toml`, and `harnesses/` declare plugins; `harness_filters.py` owns resolution; `configuration/data.toml`, `configuration/templates/`, and `configuration/assets/` declare settings and source assets. Host-local, untracked configuration overlays belong in `bootstrap/capabilities/agent-harness/local/<hostname>/data.toml`. Host-local plugin sources belong in `local/<hostname>/catalogue.toml` beside it. Native `agent-config` owns settings and assets on every registered host.

- **Plugins** at `agents/<plugin>/skills/`, listed in `.claude-plugin/marketplace.json`. A skill may be a plain `SKILL.md` or a `SKILL.md.j2` templated at deploy time, and this applies to any other `.j2` file in the skill dir. Repo-local skills live at `.agents/skills/`, symlinked into `.claude/skills/`. The `.j2` skills mean a plugin is not installable through Claude's own plugin mechanism, which does no templating — deployment goes through `agent_harness` instead. see `agents/README.md` for more.
- **The librarian** comes from `thurstonsand/pi-librarian`, which Pi installs. `claude.py` declares its marketplace with `extraKnownMarketplaces` and enables the plugin with `enabledPlugins`, everywhere but work, and Claude installs it in the background at the next session. Codex plugins cannot ship agents, so `codex.py` updates Pi's installed copy, which Pi never updates on its own, then runs `librarian codex setup` from it in a throwaway home and renders the role and rule it writes, plus `~/.local/bin/librarian` pointing at that copy. Shared settings are `~/.config/agents/librarian/config.json`, rendered by `pi.py`.
- **User-level instructions** live in `instructions/AGENTS.md.tera`; `mise run amp:guidance` renders Amp's `global_agent_guidance`.
- **Models** at `bootstrap/capabilities/agent-harness/models.yml` are the single source for versions, aliases, and per-editor config. Native renderers merge them with `configuration/data.toml` and the host overlay. `swb.py` renders agent-switchboard's shortlist from them, one preset per delegation role, and keeps the rest of swb's settings as they are on the host. Haiku's small jobs, such as Pi's and Claude Code's session titles and Pi's working vibes, call Anthropic's API directly with the metered `ANTHROPIC_API_KEY`.
- **Assets** under `configuration/assets/` are first-party source. `assets.toml` declares assets, package dependencies, and explicit retirements; an asset naming a `harness` deploys only where `profiles.toml` targets it, and `hosts` narrows host-specific content; native configuration symlinks unchanged files into `$HOME` and renders host-dependent or secret-bearing files as regular files. Never put credentials in templates, assets, or host overlays: declare SecretRefs in fnox and let `agent-config` resolve only the keys required by that host. Private outputs use mode `0600`.

Run `mise agent-config --check` to preview and `mise agent-config` to apply. `mise agent-harness` runs the catalogue first and then configuration; full host reconciliation routes both through the `agent-harness` tag.

## Browser automation

The `browsing` skill selects Browse on personal hosts and the preinstalled agent-browser in Amp orbs. It loads each CLI's own version-matched guide instead of maintaining a second copy. Work receives only the skill, rendered for the Chrome DevTools MCP server that its local overlay attaches to the running Chrome. Claude Code, Codex, and Pi receive the skill through host reconciliation; Amp receives it through User Skills publication, including on eve, which has no native agent-harness profile.

pod042, pod153, no9-type-s, and eve declare `npm:@opencode/browse` in their global mise configs. Mise owns CLI upgrades; `OPENCODE_BROWSER_AUTO_UPDATE=off` prevents Browse from installing an unmanaged npm-global copy. Reconcile the host's tool and agent-harness capabilities before using it; eve installs its tools with `mise windows -t mise`. Old agent-browser skills are explicitly retired. On hosts that had it, Browse's install hook prunes unused agent-browser versions while retaining any still used by a project or running agent. Amp's orb image is unchanged.

Each browser profile needs the official [Browse extension](https://chromewebstore.google.com/detail/mfnicocicmmlkpjnaffgihfjhdgjkdjg) and a one-time local pairing. pod042's Chromium policy installs it alongside ChatGPT and 1Password; reload `chrome://policy` after applying that policy. Other personal Chrome profiles use the Web Store and Chrome Sync. Browser profiles and pairing credentials stay out of the repo.

For CLI-only pairing, run `browse pair`, open the extension's Options, enter the displayed code under **Pairing code**, and connect to `localhost:19988`. Finish with `browse doctor` and a named-session navigation. Avoid `browse install`: it autodetects the calling harness and writes MCP configuration that this repo already owns. Even `browse install --help` runs the installer in 0.0.10. The CLI is sufficient for Pi and the other harnesses; no MCP registration is needed.

Browse cannot operate 1Password's extension UI. Existing website sessions remain useful, but a new passkey login requires a user handoff or separately authorized native desktop interaction outside a Browse-controlled tab. On shared browsers, delete only the task's session rather than running Browse's global tab cleanup.

## Publishing Amp User Skills and Plugins

`publish_amp_skills.py --repo . --output DIR` renders the `amp_publish` profile through the same `render_files` path the hosts use and writes only the Amp skills tree into an empty `DIR`: Git sources are cloned fresh into a throwaway cache (or `--cache DIR`, with `--cached` to skip the refresh), hook fragments are never emitted, and nothing under the operator home is read or written. `scripts/publish-amp-skills.sh` runs it and syncs the result into the hosted User Skills repository; the GitHub workflow does the same on push. A skill that names `amp` as an explicit target overrides the profile.

`amp-plugins/` contains the first-party global User Plugins sources: root `.ts`/`.js` files or directory plugins with `index.ts`/`index.js`. `scripts/publish-amp-plugins.sh` updates only those root paths in the hosted repository, including removal of obsolete files inside an owned directory, and preserves all other plugins. Removing a root source does not delete its hosted plugin; retire that path explicitly in the hosted repository. Tests live outside `amp-plugins/` so they are never published. Both publishing scripts accept `--dry-run` to prepare and report a diff without committing or pushing. The shared workflow tests the plugins and publisher, then publishes plugins and skills on relevant `main` pushes and daily. It uses the existing `AMP_API_KEY` secret. New threads load published plugins automatically; existing threads need a plugin reload.

`models.yml` also declares upstream plugins under `amp.plugins`: a source URL, model tier (`provider.key`), and reasoning effort for each. `render_amp_plugins.py --output DIR` combines the first-party sources with fresh upstream downloads in an empty staging directory, replacing only each upstream file's `MODEL` and `REASONING_EFFORT` constants. The publisher runs this on every publication, so the daily workflow follows upstream prompt and tool changes while retaining the declared models: Fable at `xhigh` for Oracle, Sol at `low` for Librarian and Finder. Missing or duplicate constant declarations fail before publication. These generated root paths are owned just like first-party plugins; retire them explicitly when removing a declaration. Use `scripts/publish-amp-plugins.sh --dry-run` to preview against the hosted repository without publishing.

First-party entries under `amp.plugins` omit `source` and receive the same model and effort overrides. An optional `instructions` path, relative to this capability, embeds the body of an agent Markdown file without its frontmatter into the plugin's `INSTRUCTIONS` constant. `amp-plugins/code-review.ts` is a publication template, not a directly installable plugin: publication gives its `code_review` tool the canonical `agents/project-management/agents/code-review.md` prompt and Astra at `high`. The reviewer retains Finder, Librarian, and parent-thread access; read-only behavior is instructed rather than filesystem-enforced. Amp's branch of `instructions/AGENTS.md.tera` routes code reviews to `code_review`, engineering advice to `oracle`, and other delegation to `Task`. Render that guidance with `mise run amp:guidance` and apply it through Amp settings separately; CI publishes plugins and skills, not global guidance.

Main-thread defaults and the model selector's Top Models are account settings, separate from plugin model pins. Configure them through [Settings → Model Selector](https://ampcode.com/settings/model-selector) or `manage_amp`; this workflow does not reconcile account settings.
