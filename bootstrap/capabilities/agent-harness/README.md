# Declarative agent harness capability

`catalogue.toml` is the single checked-in plugin catalogue. `harness_filters.py` beside it performs manifest discovery, selector handling, and the per-harness SKILL.md transforms; `models.yml` and `session-title-prompt.txt` are the canonical model catalogue and session-title prompt that those transforms, the configuration renderers, and skill templates read. Skill templates reach files in this directory through the `agent_harness_root` Jinja global. The work laptop's Ansible role loads the same module as a filter plugin through a symlink under `ansible/roles/agent_harness/filter_plugins/`; its private `agent_harness_sources_extra` support remains unchanged.

Each `harnesses/<name>/mise.toml` is a native mise project fragment. Its `[harness]` table declares destination roots and the name transform; it may also compose ordinary `[vars]`, `[dotfiles]`, and `[bootstrap.files]` resources owned by that harness. Only enabled harness fragments are applied. For example, a template stored beside the declaration can become a native dotfile:

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

A native host declaration selects a profile, enabled harnesses, explicit-only harnesses, template hostname, Jinja block policy, source update policy, and ownership manifest. The personal Mac declaration is `bootstrap/targets/Thurstons-MacBook-Pro/mise.agent-harness.toml`; pod042's is `bootstrap/targets/pod042/agent-harness/host.toml`.

`agent_harness_deploy.py` is the common deployment engine. It renders through `catalogue.py`, aggregates repeated selector rows by stable `source + plugin` identity, and records an exact per-plugin inventory. Omitting a previously deployed plugin is a no-op: all of its recorded paths and its source-plus-plugin provenance remain available for a later explicit retirement. Add that same identity with `remove = true` to retire it, including while its checkout is unavailable:

```toml
[[sources]]
repo = "owner/catalogue"

[[sources.plugins]]
name = "retired-plugin"
remove = true
```

Without inventory, removal must resolve the declaration or fail. Target and selector changes retire only paths owned by the affected plugin. Unmappable entries from the old flat Mac and pod042 manifests are retained.

Native mise dotfiles deploy unchanged local-source files as symlinks to their repository source. Files from Git checkouts are copies, while templates and harness-transformed files are real files backed by a durable rendered generation. Native absence resources remove stale exact files. Before using mise's force mode, the engine requires every existing destination to be recorded, proven by a legacy manifest, or byte/mode-equivalent to the desired deployment. Cleanup is exact-file ownership; there is no whole-directory prune.

The version 3 ownership manifest also retains a canonical, profile-resolved selector fingerprint per source-plus-plugin owner. An unchanged, previously successful declaration may lose an individually named include, exclude, or explicit-map path upstream; that resource is then retired by exact ownership. New or changed declarations remain strict, including explicit empty maps, and missing checkouts or manifests remain errors. Version 2 manifests are upgraded by strict validation against the old cache before any Git refresh; `--check` never persists that migration proof.

The ownership manifest is atomically expanded before native apply and narrowed only after success. Selector proof is retained on empty tombstones, omitted owners, and pending recovery; old rendered bytes are never replayed. Destination parents may not redirect outside the operator home; intentional local-source links may point back into the repository. `--check` requires cached Git sources and writes neither source timestamps nor managed state. `--cached` applies the fixed cache. Normal updates are every 86400 seconds on the Mac and every run on pod042. Mac templates retain `trim_blocks = true`; pod042 retains `false`.

Run `mise agent-harness [--check|--cached]` on either registered personal system. pod042 retains its hostname, UID, GID, and home guard. Work continues through Ansible until its private-source cutover.

## Publishing Amp User Skills

`publish_amp_skills.py --repo . --output DIR` renders the `amp_publish` profile through the same `render_files` path the hosts use, with `trim_blocks` on, and writes only the Amp skills tree into an empty `DIR`: Git sources are cloned fresh into a throwaway cache (or `--cache DIR`, with `--cached` to skip the refresh), hook fragments are never emitted, and nothing under the operator home is read or written. `scripts/publish-amp-skills.sh` runs it and syncs the result into the hosted User Skills repository; the GitHub workflow does the same on push.
