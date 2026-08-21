---
name: grill-me
description: Grilling and design session that challenges your plan against the existing codebase, domain model, and documented decisions; sharpens terminology; updates documentation (CONTEXT.md, design docs) inline as decisions crystallize; and produces committable implementation plans. Use when user wants to stress-test, design, or plan a feature against their project's language and documented decisions.
---

# Grill Me

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down every branch of the design tree, and for each question, provide your recommended answer.

This skill uses three gates:

1. **Grill**: challenge the plan until assumptions, terminology, constraints, and branches are resolved.
2. **Design**: turn the resolved decisions into a design document.
3. **Execution planning**: break the design into committable implementation units.

Start at Gate 1 unless the user explicitly says a gate is already complete.

## Gate 1: Grill

Map the plan as a **design tree**: every decision branches into the decisions that hang off it.

### Work the frontier

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Prefer blunt accuracy over agreeable momentum. If something looks weak, say so plainly.

### Facts are yours; decisions are the user's

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment, dispatch a sub-agent to find it; don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now.

Inspect:

- code, tests, configuration, and existing docs relevant to the plan
- existing relevant design docs in `docs/designs/`
- existing domain docs: `CONTEXT.md`, `CONTEXT-MAP.md` (if exists), and nested `CONTEXT.md` files when relevant
- public documentation or source code for major libraries or platforms when the design depends on their behavior

Cross-check the user's claims against the code, tests, configuration, and existing docs. Surface contradictions immediately.

The _decisions_ are the user's: put each to them and wait.

### Calibrate by cost of being wrong

For each major decision, ask what the cost would be if the design is wrong. Spend design attention on decisions that are hard to reverse, risky, surprising, or likely to constrain future work.

### Describe every interface and test seam

Before the design is settled, fully describe every interface the plan touches:

- the end-user surface, whatever form it takes: UI, CLI, API, file format, workflow
- boundaries between major layers or components: service ↔ database, client ↔ server, module ↔ module
- contracts with external systems and libraries

For each one, pin down what crosses the boundary: the operations, the data shapes, the failure behavior, and which side owns what.

Identify where the resulting behavior will be tested. Prefer existing seams, and choose the highest seam that proves external behavior without coupling tests to implementation details. If the design needs a new seam, make that an explicit decision.

### Challenge against the glossary

When the user uses a term that conflicts with existing language in `CONTEXT.md`, call it out immediately.

> Your glossary defines "cancellation" as X, but you seem to mean Y. Which is it?

### Sharpen fuzzy language

When the user uses vague, overloaded, or inconsistent language, stop and force a sharper definition. Propose a precise canonical term.

> You're saying "account". Do you mean the Customer or the User? Those are different things.

### Discuss concrete scenarios

Stress-test ideas with concrete scenarios and edge cases, not paraphrases of what the user just said. Invent scenarios that probe boundaries between concepts and force precision. Carry scenarios into the design doc's problem statement when they explain why the problem matters.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it.

> Your code cancels entire Orders, but you just said partial cancellation is possible. Which is right?

### Update CONTEXT.md inline

When a term is resolved, update `CONTEXT.md` right there. Don't batch these up: capture terms as they happen. Use the format in [context-format.md](./references/context-format.md).

Don't couple `CONTEXT.md` to implementation details. Only include terms that are meaningful to domain experts.

Create context files lazily, only when you have something to write. If no `CONTEXT.md` exists, create one when the first term is resolved. If `CONTEXT-MAP.md` exists, use it to find the relevant context. When multiple contexts exist, infer which one the current topic relates to; if unclear, ask.

### Question format

Format a round like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Shape choices around real paths forward. Do not turn the round into a generic questionnaire.

If code, docs, diffs, or diagrams will sharpen a decision, include them rather than paraphrasing them. Keep them small: the minimum structure needed to make the decision clear, or pseudocode when that communicates the idea better.

### Gate 1 exit

Gate 1 is complete when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Summarize:

- decisions made
- interfaces described, at every level
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

- `Draft`: still being shaped
- `Accepted`: agreed path; normal terminal state
- `Deferred`: valid, but not being pursued now
- `Rejected`: explored and intentionally declined
- `Superseded by docs/designs/NN-name.md`: old decision replaced by a newer design

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

Prefer tracer-bullet phases: each phase should deliver a narrow, complete path through every affected layer and be independently demonstrable or verifiable. If the current structure makes that difficult, plan the prefactor first. For wide mechanical migrations that cannot land as vertical slices, use expand–migrate–contract phases so intermediate commits remain stable.

Gate 3 is complete when the design doc contains a handoff-safe implementation plan.
