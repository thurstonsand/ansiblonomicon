# Design Doc Format

Design docs live in `docs/designs/` and use sequential numbering: `NN-slug.md`.

A design doc is a historical artifact. Once accepted, do not keep editing it into current-state documentation. If the design materially changes, create a new design doc and/or mark the older one superseded.

Record what was decided, why, and what tradeoff made the decision worth remembering. The doc should support implementation without becoming a changelog or current-state reference manual.

## Template

```md
# {Short title}

## Status

Draft

## Decision Summary

{1-3 sentences: what this design decides, why it exists, and the key tradeoff.}

## Problem Statement / Background

{Clear articulation of what needs to be solved and why now. Answer: why are we taking this on, what problem does it solve, and were there previous attempts? Include concrete scenarios when they support these answers.}

## Goals

- {Outcome-oriented goal; focus on desired behavior or impact, not implementation details}
- {Outcome-oriented goal}

## Non-Goals

- {Explicit scope boundary, if useful}

## Exposed Shape

{Setting aside implementation, describe every interface this design exposes: the end-user surface (UI, API, CLI, file format, workflow, or domain abstraction), boundaries between major layers or components, and contracts with external systems. For each, what crosses the boundary — operations, data shapes, failure behavior, and which side owns what. Is this the shape we want people and components interacting with?}

## Design Decisions

### 1. {Decision name}

{What was decided and why. Include the tradeoff when it matters. Include non-obvious consequences when they affect future implementation or operations.}

## Edge Cases & Failure Modes

- **{Scenario}:** {Expected handling}

## Alternatives

### {Alternative}

- **Status:** {Rejected or Open}
- {{if Rejected}}**Decision**: {why it lost}{{endif}}
- {{if Open}}**Open Issue**: {what problem remains unaddressed}{{endif}}
- **Discussion:** {Context worth preserving}
- {{if Open}}**Next step:** {what evidence or action would resolve the decision?}{{endif}}

## Implementation Plan

Break work into committable units. Each unit must leave the repository in a stable, reviewable state: tests/builds/lints pass where applicable, no half-implemented concepts are exposed, and the next person can continue without hidden context.

- [ ] Phase 1: {Name}
  - Goal:
  - Files:
  - Work:
  - Validation:
```

## Optional sections

Default to excluding these sections. Add them only when the context clearly warrants them; if unclear, ask the user.

### Operational Considerations

Use only for enterprise systems, projects with external stakeholders, or commitments to users other than the project owner where operational behavior needs explicit review. Possible contents include success metrics, SLOs, monitoring, alerting, logging, dependencies, infrastructure, rollout, and support boundaries.

### Security / Privacy / Legal

Use only when the project handles customer data, or when security, privacy, compliance, or legal risk is material. Omit for personal or self-only projects unless the user asks for it.

## Status values

Use these statuses only:

- `Draft` — still being shaped
- `Accepted` — agreed path; normal terminal state
- `Deferred` — valid, but not being pursued now
- `Rejected` — explored and intentionally declined
- `Superseded by docs/designs/NN-name.md` — old decision replaced by a newer design

## Decision quality

The design doc should make durable decisions clear, especially when they are:

- **Hard to reverse.** The cost of changing your mind later is meaningful.
- **Surprising without context.** A future reader may wonder why it was done this way.
- **The result of a real tradeoff.** There were genuine alternatives and this path was chosen for specific reasons.

Examples:

- **Architectural shape.** Using a VM instead of a Docker stack.
- **Integration patterns.** Communicating via domain events rather than synchronous HTTP.
- **Technology choices that carry lock-in.** Database, message bus, auth provider, deployment target; not every library.
- **Boundary and scope decisions.** The explicit no-s are as valuable as the yes-s.
- **Deliberate deviations from the obvious path.** These stop future engineers from "fixing" something that was deliberate.
- **Constraints not visible in the code.** Compliance, latency requirements, operational limits, hardware constraints.
- **Alternatives when the outcome is non-obvious.** If someone is likely to suggest the same path again, record why it lost or what remains unresolved.

## Implementation plan rules

Implementation plans are not ordinary task lists. They are handoff-safe increments.

Each phase must:

- be independently committable
- leave the repository stable
- keep tests, builds, and linters passing where applicable
- avoid broken intermediate states
- avoid exposing half-finished concepts
- include enough validation that the next person can trust the boundary
- make clear what has and has not been completed
- prefer phases that create reviewable artifacts early

Prefer this structure for each phase:

```md
- [ ] Phase N: {Name}
  - Goal: {What this phase accomplishes}
  - Files: {Expected files or areas touched}
  - Work: {Concrete implementation tasks}
  - Validation: {Commands/checks/manual verification}
```
