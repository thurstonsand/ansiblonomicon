---
name: updating-documentation-for-changes
description: Use at the end of a unit of work, before commit or PR, to verify related documentation matches the new state
---

# Updating Documentation for Changes

Use this when wrapping up a unit of work. The mission is narrow: verify related documentation matches the new state before commit or PR, without turning the change into a general documentation cleanup.

## Scope

Check documentation against the staged diff only.

```bash
git diff --staged --name-only
git diff --staged
```

If nothing is staged, stop and ask for the intended diff or for changes to be staged first.

Do not fix unrelated stale documentation in this pass. After completing updates, flag it to the user as potentially needing addressing.

## Documentation Categories

### Design docs

Design docs are historical records by default. Do not update old design documents just because implementation has moved on.

Update a design doc only when both are true:

- the staged work is actively implementing that design
- implementation required changes to decisions, constraints, or details that were originally specified in that design

When updating an active design doc, write it as the design that was intended. Do not preserve obsolete state or explain that something used to work differently.

If staged work materially replaces an accepted design, mark the older design doc status as superseded. Keep the rest of the superseded doc intact.

### Agent docs

Agent docs describe how future agents should operate in the repo. This includes files like `CLAUDE.md`, `AGENTS.md`, skill files, local agent instructions, and similar guidance.

Update them when the staged change affects:

- commands agents should run
- repo conventions or workflows
- architecture or deployment assumptions agents rely on
- known hazards, required skills, or operational procedures

Keep these docs directive and practical.

### User docs

User docs are everything meant to help the human configure, deploy, or understand the project: READMEs, guides, API docs, examples, changelogs, package metadata, deployment notes, and similar files.

Update them when the staged change affects user-visible behavior, configuration, commands, APIs, installation, deployment, examples, or troubleshooting.

Do not add internal architecture detail to user-facing docs unless users need it to make correct decisions.

## Pass 1: Find Expected Docs

From the staged diff, identify the feature, command, API, config, workflow, or behavior being changed. Then inspect the documentation locations that are likely to describe it.

Common places:

- nearby docs in the changed package, role, app, or module
- repo-level docs
- docs directories
- examples and config templates
- package metadata or manifests that expose commands, APIs, descriptions, or entry points
- agent instruction files when agent behavior is affected
- active design docs when the change implements that design

Read each relevant document to understand its purpose, audience, current style, and level of detail to ensure updates match.

## Pass 2: Search for Unexpected Docs

After checking the obvious places, search for references that may live elsewhere.

Use terms from the diff: feature names, command names, flags, config keys, API paths, class/module names, service names, and user-facing concepts.

Example patterns:

```bash
rg "feature-or-command-name" -g "*.md" -g "*.mdx" -g "*.rst" -g "*.txt" -g "*.json" -g "*.yaml" -g "*.yml"
rg "config_key|related concept|old behavior" docs .github agents .agents 2>/dev/null
```

Follow direct cross-references if clearly related.

## Deciding What to Change

Update documentation when a reader relying on the current docs would be misled, surprised, or missing important information because of the staged change.

Usually update docs for:

- new or changed commands, flags, APIs, configuration, workflows, or deployment steps
- removed or renamed behavior that docs still mention
- examples that no longer work
- agent instructions that would cause future agents to do the wrong thing
- active design docs whose implementation details changed during the work

Usually do not update docs for:

- internal refactors with no documented behavior change
- bug fixes that restore documented behavior
- implementation details that do not belong to the doc's audience
- unrelated stale content found during the sweep
- historical design docs that are not the design currently being implemented

## Writing Updates

Match the document you are editing.

- Preserve its audience, tone, structure, and level of detail.
- Put information where that document's reader would look for it.
- Prefer concise corrections over broad rewrites.
- Describe the current state directly. Do not add changelog language like "previously X, now Y" unless the document is explicitly a changelog.
- Verify examples, commands, links, and cross-references still make sense.

If the right update would be large or contentious, stop and report the documentation gap instead of guessing.

## Finish

After updating docs:

1. Review the doc diff against the staged code diff.
2. Confirm the documentation change is related to the staged work.
3. Note unrelated stale docs separately, if found.
4. Stage only the documentation updates that belong with this change.

The end state: related docs are current, historical docs stay historical, and the commit remains focused.
