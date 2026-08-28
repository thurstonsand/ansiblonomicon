# agents/

Skill plugins deployed by the `agent_harness` role. Each directory here is one plugin, listed in `.claude-plugin/marketplace.json` and wired up in `ansible/agent-harness.config.yml`.

Most of what a harness ends up with is pulled verbatim from upstream repos and never lands in this tree. This file covers the exceptions: skills we fork rather than consume, and therefore have to re-sync by hand. Two upstreams so far, [mattpocock/skills](https://github.com/mattpocock/skills) and [cursor/plugins](https://github.com/cursor/plugins).

## Ours outright

Written here, no upstream lineage, nothing to sync.

| plugin             | skills                                                        |
| ------------------ | ------------------------------------------------------------- |
| project-management | `commit-msg`, `gc`, `update-docs`, `tui-screenshot`, `notify` |
| claude             | `retitle`                                                     |
| codex              | `embrace-vet-claims`                                          |
| homelab            | `truenas-docker-ops`                                          |

Repo-local skills at `.agents/skills/` (`cloudflare-ops`, `installing-software`) are ours too, symlinked into `.claude/skills/` rather than deployed.

## Adapted from mattpocock/skills

None of these is on the `include_skills` list for the `mattpocock-skills` plugin, so ours wins: that plugin admits five upstream skills by name and nothing else. Upstream keeps moving, so each row records the upstream commit our copy was last reconciled against.

| ours                                               | upstream                                                        | synced to            | divergence                                                                                                                                                                                                                                  |
| -------------------------------------------------- | --------------------------------------------------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `project-management/grill-me`, `pi/grill-me`       | `productivity/grill-me` + `grilling`                            | `0ab1b63` 2026-08-20 | Upstream's `grill-me` is a shim over `grilling`; ours is the whole workflow in three gates, with context and design formats as local references. The pi variant asks rounds through pi's `interview` tool instead of the markdown template. |
| `project-management/wayfinder`                     | `engineering/wayfinder`                                         | `0ab1b63` 2026-08-20 | Upstream abstracts the map behind an issue tracker. Ours stays markdown under `docs/wayfinding/`, computes the frontier with `scripts/frontier.py`, and carries a `prototype.md` reference adapted from `engineering/prototype`.            |
| `project-management/improve-codebase-architecture` | `engineering/improve-codebase-architecture` + `codebase-design` | `0ab1b63` 2026-08-20 | Cross-skill calls collapsed into local `references/`, ADRs replaced by `docs/designs/`, `grilling` and `domain-modeling` replaced by `/grill-me` gates.                                                                                     |
| `project-management/wait-what`                     | `productivity/wait-what`                                        | `0ab1b63` 2026-08-20 | One line, fully rewritten. Ours names the failure mode; upstream asks for Simplified Technical English.                                                                                                                                     |
| `claude/handoff`                                   | `productivity/handoff`                                          | `0ab1b63` 2026-08-20 | Templated `.j2` rewrite, three times the length, so it cannot ship through Claude's own plugin mechanism.                                                                                                                                   |

The pattern: where upstream splits a workflow across skills that call each other, we collapse it into one skill with local reference files. That is why upstream's cross-skill churn mostly misses us.

## Adapted from cursor/plugins

Not installed as plugins, so nothing here is on an exclude list. These are copies that have to be re-synced by hand.

| ours                             | upstream                                                                                   | synced to            | divergence                                                                                                                                                                                                                                                                                                                                     |
| -------------------------------- | ------------------------------------------------------------------------------------------ | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `project-management/interrogate` | `pstack/interrogate`                                                                       | `51a96e0` 2026-08-21 | Replaces our fork of `thermos/thermo-nuclear-code-quality-review`, which this is upstream's own refinement of. Carries over that fork's scope workflow (branch, uncommitted, staged, commit range), its change framing in place of PR framing, its 2B review tone, and its model invocability. Reviewers are named by family rather than slug. |
| `project-management/implement`   | `pstack` Feature and Autonomous run playbooks, subagent rules, `blast-radius`, `architect` | `51a96e0` 2026-08-21 | Assembled rather than forked; upstream has no single skill for this. Runs only on an approved plan, user-invoked so it cannot fire mid-discussion, never commits or stages, and hands back artifacts rather than prose. Unrelated to Matt Pocock's excluded `implement`.                                                                       |
| `project-management/reflect`     | `pstack/reflect`                                                                           | `51a96e0` 2026-08-21 | Harness-agnostic transcript location and subagent spawning, models named by role rather than slug, `create-skill` becomes `writing-for-agents`, no backlog tracker, and edits route to the source skill in this repo rather than the deployed copy.                                                                                            |

Upstream's pstack is built around a Cursor-only sticky mode skill, per-role model config in `~/.cursor/rules/`, Graphite stacks, and cloud workers. Its playbook layer does not port. Its lenses, rubrics, and principles do.

## Borrowed without a skill

Ideas lifted into skills we already own, with no upstream file to track.

| where                                               | from                                                                                                                                                                                                                                                                      |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `grill-me/references/design-format.md`, call stacks | [dmmulroy/skills](https://github.com/dmmulroy/skills) `tech-spec` and humanlayer's [Why Software Factories Fail](https://github.com/humanlayer/advanced-context-engineering-for-coding-agents/blob/main/wsff.md), which credits Dillon Mulroy for call graphs in planning |

## Taken verbatim

Not excluded, so they deploy straight from the upstream checkout and update on every reconcile: `resolving-merge-conflicts`, `wizard`, `writing-for-agents`, `teach`, `to-questionnaire`.

## Left out

Excluded with no local counterpart.

- `ask-matt`, `code-review`, `diagnosing-bugs`, `domain-modeling`, `grill-with-docs`, `implement`, `research`, `tdd`, `to-spec`, `prototype`: workflow opinions we declined, or content already absorbed. `research` lives inside wayfinder's research ticket type; `prototype` inside its `references/prototype.md`.
- `to-tickets`: it is execution planning, which is `/grill-me` Gate 3. Wayfinder ends where Gate 3 begins, so it has no home here.
- `triage`: a maintainer's inbox for inbound issues and external PRs. No repo here has one.
- `setup-matt-pocock-skills`: provisions the issue tracker docs our wayfinder fork does not use.
- `codebase-design`, `grilling`, `grill-me`: excluded because they were absorbed, not because they were rejected. `grilling` is the live sync channel: it is the primitive our `grill-me` inlines, so upstream edits to it are the ones that still reach us.

Upstream's `misc/` and `in-progress/` trees are not in its plugin manifest, so we never see them.

## Running an import

The harness cache at `~/.cache/ansiblonomicon-harness/mattpocock--skills` is a shallow clone, so diffing against it does not work. Clone fresh, then diff from the commit in the table above:

```sh
git clone https://github.com/mattpocock/skills.git /tmp/mp-skills
cd /tmp/mp-skills && git diff <synced-to> main -- skills/<path>
```

Read the commit subjects first. Upstream does repo-wide prose passes (an em-dash purge, a skill-invocation terminology sweep) that touch every file we fork and change nothing. Filter those out, take what is substantive, and where a rewrite does apply, match upstream's wording so the next diff stays clean. Then update the table and add a log entry below.

## Import log

### 2026-08-21, cursor/plugins `51a96e0`

Added `reflect`, close to upstream's wording. Cursor's transcript layout, `Task` spawning, and per-role model rules are replaced with harness-agnostic descriptions, since these skills deploy to six harnesses and may not name a tool. One addition with no upstream counterpart: reviewers cite the deployed skill path, so the parent has to map it back to the source in this repo before editing, or the next reconcile overwrites the work.

Retired `thermo-nuclear-code-quality-review` in favour of `interrogate`. The two share ancestry: pstack's `interrogate/references/code-quality-review.md` is the same rubric compressed from 192 lines to 47, with the identical core prompt and the same eight dimensions, stated once instead of restated across five sections. What it adds is a second rubric covering correctness, root causes, structural integrity, verification, and complexity budget, plus multi-model fan-out and a lead-judgment pass that sorts findings into act on, consider, noted, and dismissed rather than aggregating them. Only Codex needs an `.ansibleremove` entry, since every other harness prunes orphaned skills on reconcile.

Added `implement`, assembled from five upstream sources, because pstack spreads this workflow across a playbook layer that does not port. Deliberately decoupled from `grill-me`, with no cross-reference in either direction and `disable-model-invocation: true` so it cannot fire while a plan is still being argued. Three rules are ours. The plan is a contract, so a real problem with it stops the run rather than triggering a redesign. Nothing is committed or staged, since the staged split is the review ledger. The hand-back is artifacts to look at rather than prose to read.

Added call stacks to `grill-me/references/design-format.md`, taken from `tech-spec`'s call-stack section and humanlayer's call-stack-tree diff format. Type sketches were deliberately not taken; a call stack pins ownership and order, which survives implementation drift, where signatures do not.

Established that `thermo-nuclear-code-quality-review` was a fork of cursor's `thermos` plugin. It was retired the next day; see the entry above.

### 2026-08-20, upstream `0ab1b63`

Full review of every skill in the plugin manifest against ours, recorded above.

Adopted: upstream `85f83d3`, which separates consecutive questions in a grilling round with a horizontal rule, into `project-management/grill-me` only. The pi variant routes rounds through `interview` and has no markdown template to separate.

Adopted independently: upstream's em-dash purge (`3216582`), applied to every skill we author, including ones with no upstream lineage. Where upstream had rewritten the same sentence, we matched its wording.

Declined: the `call the Skill tool with "name"` phrasing (`d28dfdc`, `fcf0071`, `447ca70`). It is Claude-specific and we deploy to six harnesses. Declined the `wait-what` CONTEXT-MAP pointer, since ours is a rewrite and no repo here has more than one CONTEXT.md. Declined the wayfinder change telling the user to run `/setup-matt-pocock-skills`, which our fork has no use for.

Config: deleted the `work` entry in `exclude_skills_by_profile`. It had drifted, still naming the long-deleted `to-issues` and `to-prd`, and it let work install Matt's `improve-codebase-architecture` while excluding the `codebase-design`, `grilling`, and `domain-modeling` skills that it calls. Work now uses the same exclusions as everything else, so it takes our forks instead of Matt's.

Config: `excluded_on: [work]` moved off the whole `- local:` source and onto the `homelab` plugin, which was the only one meant to be dropped. Work had been losing every skill in this tree. `tui-screenshot` is excluded there separately, since it drives tuistory and the work mirror cannot install it.

Added: `wayfinder/references/prototype.md`, taken from `engineering/prototype` with its `LOGIC.md` and `UI.md` inlined, at 97% of upstream's wording. Kept as a reference rather than a standalone skill because prototyping only comes up here inside wayfinding. Two deviations: the capture step records to the ticket's `## Resolution` and `docs/wayfinding/<effort-slug>/prototypes/` rather than to an issue tracker, and "throwaway" is replaced throughout by the property it means here, that the code never ships.

### 2026-08-09, upstream `84fdeff` (inferred)

Local commit `d81356c`. Added `improve-codebase-architecture` and `wait-what` as forks, dropped `to-issues` and `to-prd`, and rewrote `grill-me` Gate 1 around the frontier-of-rounds model. Baseline commit is inferred as the last upstream commit before that date; entries before this one predate the log, and the local git history is the record.
