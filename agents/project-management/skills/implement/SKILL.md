---
name: implement
description: "Execute an approved plan end to end: delegate the code, review the diff, verify against the predicate, and hand back evidence. Use when the user has approved a plan and asks for it to be implemented."
disable-model-invocation: true
---

# Implement

**You own the plan. Ground, delegate, review, verify.** Delegate implementation. Stay in the lead.

This runs after the plan is agreed, and the user invokes it deliberately. Nothing here decides anything. The plan is a contract, not a proposal.

## Start

Open a todo list with one entry per phase before starting.

1. Ground
2. Predicate
3. Delegate
4. Review
5. Verify
6. Hand back

## Phase A: Ground the plan

Load the approved plan: a design doc under `docs/designs/`, a wayfinder ticket, or the conversation that just ended. Read what it names, in the code, before spawning anything. Naming a file isn't grounding.

Restate the scope in a few lines: what gets built, what does not, and which files are in play. Then proceed. This is the last checkpoint before the hand-back, so everything after it runs without the user.

Do not re-open decisions. If grounding turns up a real problem, a decision the plan never made, a constraint that contradicts it, a file that isn't there, stop and say so. Returning to planning costs one turn. Implementing the wrong plan costs the run.

## Phase B: State the predicate

State the exit condition as a checkable predicate before the first delegation: tests green, repro fixed, the reconcile clean, the render matching.

Take it from the plan's validation steps. A phase with no validation is a defect in the plan, so name the gap and derive the predicate yourself rather than running without one.

## Phase C: Delegate

Delegate code-writing to a subagent with a specific scope (file paths, the named data shape, and success criteria). Review its diff yourself. Mandatory: no skip-with-reason escape, and "the change is small" does not override it. The gain is review separation, not lines saved. You can spawn a subagent even though you are one. A subagent forbidden to spawn satisfies this by owning the diff directly with the same review separation. No "standing by" reply that waits on a nested agent.

Pass file pointers, not inlined context. Tier the work by difficulty. The hardest changes (cross-cutting design, gnarly concurrency, subtle algorithms) go to the strongest model, whether the task needs judgment on vague intent or is a precisely specified sequence of steps to execute to the letter. Trivial mechanical edits go to the fast code model. The repo's model table names which model currently fills each role, including any that need the user's permission before spending.

One implementer is the default. Fan out only across genuine seams, where the work touches disjoint files and produces independent artifacts. Shared writes serialize. If one worker is best, that is the answer. Say why and move on.

Sequence the work into units that each end in a check, and verify each before starting the next instead of batching the edits and verifying once at the end. A break caught at the unit that caused it is cheap to localize. A break caught after a batch is buried, and you have already built further on a broken base.

Writing, changing, or keeping a test: read and apply [Test Behavior, Not Implementation](./references/test-behavior-not-implementation.md). Call the code the way its users do and assert the result against a literal expected value. If the test would still pass when every imported function returns `undefined`, rewrite the assertion or delete the test.

The implementer does not commit and does not stage. Permission rules already block subagents from altering git state, so this is a fact rather than a request. Everything lands in the working tree. The staged split is the user's review ledger and belongs to them.

## Phase D: Review

Run the `interrogate` skill over the diff. Give it the plan's intent, so the reviewers challenge whether the code achieves it rather than whether the intent was right.

You own every subagent's work. Review the diff and write your own summary, don't pass through what it said.

Route the findings you accept back to the implementer. Small corrections continue with the same one. When the scope changes materially, fire a fresh subagent with consolidated scope rather than trusting a "done" summary, because interrupt-chained resumes silently drop directives.

Loop until the review is clean. Each iteration makes the smallest change the evidence justifies. Belt-and-suspenders that "might help" gets reverted, not left to ride.

## Phase E: Deviations from the plan

Deviations are signal worth surfacing, not friction to absorb silently. When the implementation needs something the plan didn't anticipate, decide whether the plan was wrong, the requirement was missed, or the implementation is overreaching. Record it for the hand-back.

The signal to stop is a pattern, not single instances. Tells:

- The same shape of workaround appearing repeatedly across unrelated code.
- Multiple unrelated edge cases that all need special-case branches.
- Types that need escape hatches to compile.
- Callers having to know the abstraction's internal rules to use it.
- Two or more independent deviations of the same shape.

When the pattern shows, stop the run and hand back what the plan missed. Do not redesign mid-run. The user owns the plan.

When two or more fixes that share one premise have failed the same gate, read and apply [Attack the Premise](./references/attack-the-premise.md). Take a census of which actors hold the imbalance before the next fix, then question the premise instead of writing another fix that assumes it. Proceed only when the root fix fits the plan. Otherwise stop and hand back the evidence that invalidated its contract.

## Phase F: Verify

Verify on the matching surface. "Inconclusive" or wrong-surface is not a pass. Flag it.

Trust artifacts, not self-reports. Inspect the real output, the diff, the file contents, the runtime behavior, rather than the delegate's summary. Agents report what they intended, not always what happened.

For each fact the predicate depends on, get as far down this list as is cheap, and say where it stopped.

1. You said so. Worthless on its own.
2. You pointed at the line. A real `file:line`.
3. You showed the bad case can't happen. You walked the failure step by step and it doesn't reach.
4. You ran it. A script or test that calls the real code and fails loud if you're wrong.
5. You reproduced it in the running system.

Anything you can't get to step 4, say so. Don't write it up as settled.

The strongest proof is a deterministic script that re-runs the same comparison, not a one-time eyeball. Write the script, run it, and keep its output as an artifact the user can re-run instead of trusting your word.

Then hand the user something to look at rather than read: a screenshot, a rendered artifact, a before and after measurement, the log lines that prove the path executed, the reconcile output. Prose describing a passing check is the weakest evidence available and the easiest to fake by accident.

## Phase G: Hand back

Stop when the predicate is met. A plateau is not a stop, so keep going and pivot the approach to push past it. Surface a genuine dead end rather than spinning, and never relax the predicate to declare victory.

Mid-run discoveries are yours. Broken tooling, related bugs, flaky checks, and fixable drift get handled as you find them. Do not park reversible work for the user. Surface only irreversible actions, genuine preference calls no experiment can settle, or a real dead end.

**Reply:** the predicate and its final state, what was built, the evidence artifacts with their paths, deviations from the plan, what you fixed along the way, and confirmation that the work is unstaged and ready to review.
