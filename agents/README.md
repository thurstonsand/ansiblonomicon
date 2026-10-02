# agents/

Locally authored skill plugins deployed by the agent harness capability. Each directory here is one plugin, listed in `.claude-plugin/marketplace.json` and selected for deployment from `bootstrap/capabilities/agent-harness/catalogue.toml`.

Most of what a harness ends up with is pulled verbatim from upstream repos and never lands in this tree. This file covers the exceptions: skills we fork rather than consume, and therefore have to re-sync by hand. One upstream so far, [mattpocock/skills](https://github.com/mattpocock/skills); [cursor/plugins](https://github.com/cursor/plugins) lineage was retired on 2026-09-29.

## Ours outright

Written here, no upstream lineage, nothing to sync.

| plugin             | skills                                                        |
| ------------------ | ------------------------------------------------------------- |
| project-management | `commit-msg`, `gc`, `update-docs`, `tui-screenshot`, `notify` |
| claude             | `retitle`                                                     |
| codex              | `embrace-vet-claims`                                          |
| homelab            | `operating-pod042`, `operating-home-assistant`                |

Repo-local skills at `.agents/skills/` (`cloudflare-ops`, `installing-software`) are ours too, symlinked into `.claude/skills/` rather than deployed.

## Adapted from mattpocock/skills

None of these is on the `include_skills` list for the `mattpocock-skills` plugin, so ours wins: that plugin admits four upstream skills by name and nothing else. Upstream keeps moving, so each row records the upstream commit our copy was last reconciled against, and the import level (see [Running an import](#running-an-import)).

| ours | upstream | level | synced to | divergence |
| --- | --- | --- | --- | --- |
| `project-management/grill-me`, `pi/grill-me` | `productivity/grill-me` + `grilling` | adapted | `d81f3a1` 2026-09-29 | Upstream's `grill-me` is a shim over `grilling`; ours is the whole workflow in three gates, with context and design formats as local references. The pi variant asks rounds through pi's `interview` tool instead of the markdown template. |
| `project-management/wayfinder` | `engineering/wayfinder` | adapted | `d81f3a1` 2026-09-29 | Upstream abstracts the map behind an issue tracker. Ours stays markdown under `docs/wayfinding/`, computes the frontier with `scripts/frontier.py`, and carries a `prototype.md` reference adapted from `engineering/prototype`. |
| `project-management/improve-codebase-architecture` | `engineering/improve-codebase-architecture` + `codebase-design` | adapted | `d81f3a1` 2026-09-29 | Cross-skill calls collapsed into local `references/`, ADRs replaced by `docs/designs/`, `grilling` and `domain-modeling` replaced by `/grill-me` gates. |
| `claude/handoff` | `productivity/handoff` | adapted | `d81f3a1` 2026-09-29 | Templated `.j2` rewrite, three times the length, so it cannot ship through Claude's own plugin mechanism. |
| `project-management/implement` | `engineering/implement` + `tdd` | adapted | `d81f3a1` 2026-09-29 | Upstream's shape and wording, minus TDD and the commit. Keeps our plan-as-contract stop, predicate, verification ladder, and unstaged hand-back. The main agent writes the code. Inlines `tdd`'s implementation-coupled and tautological anti-patterns, plus three from pstack's Test Behavior, Not Implementation, so they load every run. |
| `project-management/code-review` | `engineering/code-review` | adapted | `d81f3a1` 2026-09-29 | Upstream's two axes and smell baseline verbatim. Scope also covers uncommitted and staged changes; the spec is the agreed plan or design rather than an issue; standards come from `AGENTS.md`, `DEV.md`, and `CONTEXT.md`; the two test anti-patterns join the baseline. Reviewers are the Oracle where the harness has one, otherwise subagents. |
| `project-management/gc` `references/pr-body.md` | `engineering/pr` | light edit | `d81f3a1` 2026-09-29 | Mermaid bullet removed, since Bitbucket Data Center does not render it (BSERV-12548), and `GLOSSARY.md` read as `CONTEXT.md`. `references/pr.md` wraps it in our gather, draft, approve, create loop. Upstream credits Dex Horthy's humanlayer `show-me` for the Summary visuals. |
| `project-management/retro` | `engineering/retro` | light edit | `d81f3a1` 2026-09-29 | `CODING_STANDARDS.md` becomes `DEV.md`, with a `CONTEXT.md` line beside it, and the Claude-specific Skill tool call becomes a plain load. |

The pattern: where upstream splits a workflow across skills that call each other, we collapse it into one skill with local reference files. That is why upstream's cross-skill churn mostly misses us.

## Borrowed without a skill

Ideas lifted into skills we already own, with no upstream file to track.

| where                                                 | from                                                                                                                                                                                                                                                                      |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `implement`, plan-as-contract and verification ladder | cursor/plugins [`pstack`](https://github.com/cursor/plugins) Feature and Autonomous run playbooks, forked here until 2026-09-29                                                                                                                                           |
| `grill-me/references/design-format.md`, call stacks   | [dmmulroy/skills](https://github.com/dmmulroy/skills) `tech-spec` and humanlayer's [Why Software Factories Fail](https://github.com/humanlayer/advanced-context-engineering-for-coding-agents/blob/main/wsff.md), which credits Dillon Mulroy for call graphs in planning |

## Taken verbatim

Not excluded, so they deploy straight from the upstream checkout and update on every reconcile: `wizard`, `writing-for-agents`, `teach`, `to-questionnaire`.

## Left out

Excluded with no local counterpart.

- `ask-matt`, `diagnosing-bugs`, `domain-modeling`, `grill-with-docs`, `implement-spec`, `research`, `tdd`, `to-spec`, `prototype`: workflow opinions we declined, or content already absorbed. `research` lives inside wayfinder's research ticket type; `prototype` inside its `references/prototype.md`; `tdd`'s test anti-patterns inside `implement` and `code-review`.
- `to-tickets`: it is execution planning, which is `/grill-me` Gate 3. Wayfinder ends where Gate 3 begins, so it has no home here.
- `triage`: a maintainer's inbox for inbound issues and external PRs. No repo here has one.
- `wait-what`: no longer needed.
- `setup-matt-pocock-skills`: provisions the issue tracker docs our wayfinder fork does not use.
- `codebase-design`, `grilling`, `grill-me`: excluded because they were absorbed, not because they were rejected. `grilling` is the live sync channel: it is the primitive our `grill-me` inlines, so upstream edits to it are the ones that still reach us.

Upstream's `misc/` and `in-progress/` trees are not in its plugin manifest, so we never see them.

## Running an import

The harness cache at `~/.cache/ansiblonomicon-harness/mattpocock--skills` is a shallow clone, so diffing against it does not work. Clone fresh, then diff from the commit in the table above:

```sh
git clone https://github.com/mattpocock/skills.git /tmp/mp-skills
cd /tmp/mp-skills && git diff <synced-to> main -- skills/<path>
```

Read the commit subjects first. Treat prose, punctuation, and formatting passes as substantive. Then pick the lightest level that works:

1. **Verbatim**: the skill is self-contained and needs no change. Add it to `include_skills`.
2. **Light edit**: copy upstream's text verbatim, then make the smallest edits that fit it here. A diff against upstream shows only those edits.
3. **Adapted**: migrate concepts rather than text, where upstream's wording conflicts with this repo's structure, harness-neutral deployment, or a deliberate local workflow decision. Keep as much upstream wording as the intent allows.

Then update the table and add a log entry below.

## Import log

### 2026-09-29, upstream `d81f3a1`

Release v1.3. Upstream deleted `resolving-merge-conflicts` (`daa01d8`) with no replacement, so it leaves `include_skills` here too; the stale name had failed the scheduled Amp publish. Deleted our `wait-what` fork, no longer needed. Deleted our `reflect` fork of `pstack/reflect`, since `retro` covers the same ground.

Introduced the three import levels described under [Running an import](#running-an-import). Every light edit also gains an H1, which this repo's markdownlint requires and upstream omits.

Light edit: `retro` (`a7d038f`), reframed onto the `AGENTS.md`, `CONTEXT.md`, `DEV.md` trio, with `DEV.md` in place of `CODING_STANDARDS.md`. `pr` (`d75dcf1` through `c55ee46`) as `gc/references/pr-body.md`, replacing our template, minus Mermaid. `gc/references/pr.md` keeps our gather, approve, and create steps and drops its `gh` recipe, since not every repo is on GitHub.

Adapted: `implement` and `code-review` replace our pstack-derived `implement` and `interrogate`, retiring that lineage. `interrogate` is renamed to upstream's `code-review`. Its multi-model fan-out, lead-judgment buckets, correctness rubric, code-quality lens, and 2B tone give way to upstream's Standards and Spec axes. `implement` drops subagent delegation, model tiering, and the Attack the Premise principle. It keeps the plan-as-contract stop, the predicate, a compressed verification ladder, and the unstaged hand-back. It is now model-invocable. Declined `tdd` and the red-green loop. Took its implementation-coupled and tautological anti-patterns, inlined in both skills so they load every run, and dropped horizontal slicing, which only matters test-first. `implement` also keeps pstack's `undefined` check, its mock-or-absence, constant-pin, and fixture-asserts-fixture shapes, and its fix and keep rules in the same list.

Declined: the `CONTEXT.md` to `GLOSSARY.md` rename (`e484a80`). `CONTEXT.md` is this repo's convention, and it is the only change upstream made to `improve-codebase-architecture` and `codebase-design`. `grill-me`, `grilling`, `wayfinder`, and `handoff` did not change.

### 2026-09-09, cursor/plugins pstack 0.15.0 `71ed0d1`

Adopted the two new principles where this plugin already owns their workflows. Their prose is copied verbatim where the local structure permits it. `implement` preserves the local rule that an invalidated plan returns to the user rather than being redesigned mid-run. Test Behavior, Not Implementation is copied into both the implementation and review paths because this plugin has no sticky mode to load the principle for them.

Adopted the release's punctuation, formatting, and mannered-prose deletions throughout shared passages in `interrogate` and the Feature, Autonomous run, `blast-radius`, `architect`, and subagent material assembled into `implement`. Kept local scope selection, model-family selection, review tone, plan ownership, staging, and hand-back rules where no upstream equivalent fits the harness-neutral workflow.

### 2026-08-21, cursor/plugins `51a96e0`

Added `reflect`, close to upstream's wording. Cursor's transcript layout, `Task` spawning, and per-role model rules are replaced with harness-agnostic descriptions, since these skills deploy to six harnesses and may not name a tool. One addition with no upstream counterpart: reviewers cite the deployed skill path, so the parent has to map it back to the source in this repo before editing, or the next reconcile overwrites the work.

Retired `thermo-nuclear-code-quality-review` in favour of `interrogate`. The two share ancestry: pstack's `interrogate/references/code-quality-review.md` is the same rubric compressed from 192 lines to 47, with the identical core prompt and the same eight dimensions, stated once instead of restated across five sections. What it adds is a second rubric covering correctness, root causes, structural integrity, verification, and complexity budget, plus multi-model fan-out and a lead-judgment pass that sorts findings into act on, consider, noted, and dismissed rather than aggregating them.

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
