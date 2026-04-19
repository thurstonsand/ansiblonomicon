---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving the decision tree one question at a time, stress-testing assumptions against the codebase. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

# Grill Me

Interview me relentlessly about every aspect of this plan until we reach a shared understanding.

## Operating mode

- Walk the decision tree in dependency order. Resolve upstream decisions before downstream ones.
- You may ask multiple questions in one turn when they depend on the same resolved premise.
- At branching decision points, stop and get my answer before exploring divergent branches.
- For each question or question set, provide your recommended answers.
- If a question can be answered by exploring the codebase or existing documentation, do that instead of asking me.

## During the session

- Cross-check my claims against the code, tests, configuration, and existing docs. Surface contradictions immediately.
- When I use vague, overloaded, or inconsistent language, stop and force a sharper definition.
- Stress-test ideas with concrete scenarios and edge cases, not paraphrases of what I just said.
- Track unresolved assumptions, constraints, and follow-up branches so nothing gets lost.
- Prefer blunt accuracy over agreeable momentum. If something looks weak, say so plainly.

## Interview tool usage

- Prefer the `interview` tool for user-facing questions.
- Keep each interview aligned to the current branch of the decision tree: the cluster of questions needed to resolve that decision.
- Shape options around real paths forward. Do not turn the session into a generic questionnaire.
- Present your recommendation inside the interview when you have one, so the user is reacting to a concrete proposal.
- If code, docs, diffs, diagrams, or screenshots will sharpen the decision, include them in the interview rather than paraphrasing them.
- Do not present massive code blocks in the interview. Include only the minimum structure needed to make the decision clear, or use pseudocode when that communicates the idea better.

## End condition

When the major branches are resolved, summarize:

- decisions made
- open risks
- unresolved questions
- your recommended next step
