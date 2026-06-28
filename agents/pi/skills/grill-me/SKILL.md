---
name: grill-me
description: Grilling and design session that challenges your plan against the existing codebase, domain model, and documented decisions; sharpens terminology; updates documentation (CONTEXT.md, design docs) inline as decisions crystallize; and produces committable implementation plans. Use when user wants to stress-test, design, or plan a feature against their project's language and documented decisions.
---

# Grill Me

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

This skill uses three gates:

1. **Grill** — challenge the plan until assumptions, terminology, constraints, and branches are resolved.
2. **Design** — turn the resolved decisions into a design document.
3. **Execution planning** — break the design into committable implementation units.

Start at Gate 1 unless the user explicitly says a gate is already complete.

## Gate 1: Grill

Walk the decision tree in dependency order. Resolve upstream decisions before downstream ones. You may ask multiple questions in one turn when they depend on the same resolved premise.

If a question can be answered by exploring the codebase, explore the codebase instead.

### Explore before asking

During codebase exploration, inspect:

- code, tests, configuration, and existing docs relevant to the plan
- existing relevant design docs in `docs/designs/`
- existing domain docs: `CONTEXT.md`, `CONTEXT-MAP.md` (if exists), and nested `CONTEXT.md` files when relevant
- public documentation or source code (using librarian) for major libraries or platforms when the design depends on their behavior

Cross-check the user's claims against the code, tests, configuration, and existing docs. Surface contradictions immediately.

### Walk the decision tree

- At branching decision points, stop and get my answer before exploring divergent branches.
- Track unresolved assumptions, constraints, and follow-up branches so nothing gets lost.
- Prefer blunt accuracy over agreeable momentum. If something looks weak, say so plainly.

### Calibrate by cost of being wrong

For each major decision, ask what the cost would be if the design is wrong. Spend design attention on decisions that are hard to reverse, risky, surprising, or likely to constrain future work.

### Challenge against the glossary

When the user uses a term that conflicts with existing language in `CONTEXT.md`, call it out immediately.

> Your glossary defines "cancellation" as X, but you seem to mean Y — which is it?

### Sharpen fuzzy language

When the user uses vague, overloaded, or inconsistent language, stop and force a sharper definition. Propose a precise canonical term.

> You're saying "account" — do you mean the Customer or the User? Those are different things.

### Discuss concrete scenarios

Stress-test ideas with concrete scenarios and edge cases, not paraphrases of what the user just said. Invent scenarios that probe boundaries between concepts and force precision. Carry scenarios into the design doc's problem statement when they explain why the problem matters.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it.

> Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?

### Update CONTEXT.md inline

When a term is resolved, update `CONTEXT.md` right there. Don't batch these up — capture terms as they happen. Use the format in [context-format.md](./references/context-format.md).

Don't couple `CONTEXT.md` to implementation details. Only include terms that are meaningful to domain experts.

Create context files lazily — only when you have something to write. If no `CONTEXT.md` exists, create one when the first term is resolved. If `CONTEXT-MAP.md` exists, use it to find the relevant context. When multiple contexts exist, infer which one the current topic relates to; if unclear, ask.

### Interview tool usage

- Prefer the `interview` tool for user-facing questions.
- Keep each interview aligned to the current branch of the decision tree: the cluster of questions needed to resolve that decision.
- Shape options around real paths forward. Do not turn the session into a generic questionnaire.
- Present your recommendation inside the interview when you have one, so the user is reacting to a concrete proposal.
- If code, docs, diffs, diagrams, or screenshots will sharpen the decision, include them in the interview rather than paraphrasing them.
- Do not present massive code blocks in the interview. Include only the minimum structure needed to make the decision clear, or use pseudocode when that communicates the idea better.

### Gate 1 exit

Gate 1 is complete when the major branches are resolved enough to summarize:

- decisions made
- open risks
- unresolved questions
- terminology/context updates made
- your recommended next step

Do not move to Gate 2 until the user agrees the design direction is ready.

## Gate 2: Design

Create a design doc unless the user explicitly says not to.

Write the design doc to `docs/designs/NN-<slug>.md`, where `NN` is the next sequential number. Use the format in [design-format.md](./references/design-format.md).

Design docs record what was decided, why, and the tradeoff that made the decision worth writing down.

### Design doc status

Use these statuses only:

- `Draft` — still being shaped
- `Accepted` — agreed path; normal terminal state
- `Deferred` — valid, but not being pursued now
- `Rejected` — explored and intentionally declined
- `Superseded by docs/designs/NN-name.md` — old decision replaced by a newer design

Once a design doc reaches `Accepted`, treat it as a historical artifact. Do not keep editing it into current-state documentation. If the design changes materially, create a new design doc or mark the old one superseded.

### Gate 2 exit

Gate 2 is complete when:

- the design doc exists
- the decision summary is clear
- the major design decisions and tradeoffs are recorded
- alternatives and open questions worth remembering are captured
- the user agrees the design is ready for planning

## Gate 3: Execution Planning

Add the implementation plan to the end of the design doc. Use the implementation-plan structure and rules in [design-format.md](./references/design-format.md).

Gate 3 is complete when the design doc contains a handoff-safe implementation plan.
