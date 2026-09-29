---
name: implement
description: "Implement an agreed plan or design, review it, verify it, and hand back evidence. Use when the user has agreed a plan and asks for it to be built."
---

# Implement

Implement the work described by the agreed plan or design: a design doc under `docs/designs/`, a wayfinder ticket, or the conversation that just ended.

Read what the plan names, in the code, before writing any. The plan is a contract: if it turns out wrong or incomplete, stop and say so rather than redesigning it mid-run.

Before starting, state the exit condition as a checkable predicate, taken from the plan's validation steps.

Write the code yourself, in small units that each end in a check.

Tests verify behavior through public interfaces, not implementation details: call the code the way its users do and assert the result they observe against a literal expected value. Before you keep a test, ask whether it would still pass if every function it imports returned `undefined`. If yes, it observes no behavior and cannot fail for a defect. Never write these:

- **Implementation-coupled**: mocks internal collaborators, tests private methods, or verifies through a side channel (querying the database instead of using the interface). The tell: the test breaks when you refactor but behavior hasn't changed.
- **Tautological**: the assertion recomputes the expected value the way the code does (`expect(add(a, b)).toBe(a + b)`, a snapshot derived by hand the same way, a constant asserted equal to itself), so it passes by construction and can never disagree with the code. Expected values must come from an independent source of truth: a known-good literal, a worked example, the spec.
- **Constant pin**: the assertion restates a hand-maintained constant, config default, table row, or prompt string: `expect(LIMITS.maxTools).toBe(8)`, `expect(PROMPT).toContain("You are")`.
- **Fixture asserts fixture**: the assertion reads data the test built or a value computed in `beforeEach`, and the subject never runs inside the body.

**The fix:** call the subject inside the test body with one concrete input and assert the literal output or the observable effect, `expect(slugify("Hello, World!")).toBe("hello-world")`. For an absence, assert the presence on the other input in the same test. For a constant, test the mechanism that reads it with one input instead of restating the value. For a mock, assert the payload it received or the state after the call, not that it was called. When no such assertion exists, delete the test.

**Keep** a test of a relation across a table's rows (a key present in two tables, a parent that exists), and a compile-time check in a `*.test-d.ts` file.

Once done, use the `code-review` skill to review the work against the plan. Fix the findings you accept.

Verify the predicate on the real surface, and say how far each claim got: pointed at the line, walked the failure through, ran it, or reproduced it in the running system. Anything short of running it is not settled. Hand the user something to look at rather than read: command output, a screenshot, the log lines that prove the path executed.

Don't commit or stage; the staged split is the user's review ledger. Reply with the predicate and its final state, what was built, the evidence, deviations from the plan, and what the review found.
