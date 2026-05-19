# Amp-style permission gate redesign

## Problem Statement

The current permission gate in `chezmoi/private_dot_pi/agent/extensions/amp-style-permission-gate/` uses `ctx.ui.confirm()`, which is only a generic Yes/No selector. That is too limited for the intended Claude Code-style permission flow.

Required changes:

- Reword the key legend around authorization language.
- `Esc` must reject the tool call **and abort the current assistant turn**.
- `Tab` on the highlighted choice must open an inline corrective-message draft inside the same gate UI.
- Drafts must wrap visually and grow vertically as needed.
- Drafts for `Authorize` and `Abort` must be preserved independently.
- `Authorize + note` must allow the tool call, wait for that tool call to finish, then surface the note inline with the resulting tool output before the assistant continues.
- `Abort + note` must reject the tool call, continue the turn with a rejection, and include the note inline in the rejection message.
- `Abort` without a note should reject the tool call and abort the turn.

## Design Decisions

### 1. Build the gate from the existing `ctx.ui.confirm()` behavior

The current `ctx.ui.confirm()` path is still the right behavioral baseline. The new gate should more or less start from that implementation — effectively copy its selector behavior and extend it — so the default feel stays aligned with the rest of pi.

The built-in selector cannot support, as-is:

- inline per-option drafts
- custom `Esc` semantics
- per-option preserved note state
- distinct post-action behavior for `Authorize + note` vs `Abort + note`
- a custom legend
- hybrid numeric-key behavior

So the extension should still use `ctx.ui.custom(...)`, but the implementation should be derived from the existing confirm/selector path rather than invented from scratch.

### 2. The gate is a single-pane interaction, not a modal editor flow

The gate starts in a compact state:

```text
1. Authorize
2. Abort
```

If `Tab` is pressed on the selected option, that option becomes editable inline:

```text
1. Authorize
2. Abort, and _
```

If text grows, the same line wraps and the gate expands vertically. This is still the same pane, not a second mode or overlay.

### 3. `Esc` always aborts when pressed during gate interaction

Final user direction:

- `Esc` from the plain selector rejects the tool call and aborts the current turn.
- `Esc` while drafting also rejects the tool call and aborts the current turn.

### 4. Draft state is stored per choice

The gate tracks two independent drafts:

- `authorizeDraft`
- `abortDraft`

Only the selected option is ever submitted, but both drafts are preserved while the gate is open.

### 5. Arrow-key behavior while drafting

When the user is actively drafting on one option and presses `Up` or `Down`:

- preserve the current draft
- move selection to the other option
- exit active editing on the old option
- if the new option already has a draft, resume editing there with the cursor at the end

This keeps navigation and editing in one surface without separate subflows.

### 6. Visibility of non-selected drafts is compact

If the non-selected option has a preserved draft, do not render the full text inline. Show a compact indicator such as:

```text
1. Authorize, and...
2. Abort, and _
```

When the user re-selects that option, restore full text and put the cursor at the end.

### 7. Numeric keys use a hybrid policy

User-selected behavior:

- Before `Tab` is ever used in the current gate, `1` and `2` may immediately select.
- After `Tab` is used once, `1` and `2` should only move selection, never immediately commit.
- While editing, numeric keys should behave like normal text input, not selection hotkeys.
- A small additional affordance is worth supporting: `Shift+Tab` should stop editing and return to a plain selection/view state, which restores numeric navigation behavior for the currently highlighted option.

This is more complex than visual-only numbering, but it matches the desired interaction model.

### 8. Post-action behavior differs by branch

#### `Authorize` without note
- Allow tool call.
- No further action.

#### `Authorize` with note
- Allow tool call.
- Wait for that tool call to complete.
- Append an authorization note block to the tool result content so the assistant sees the user's note before responding.

#### `Abort` without note
- Reject tool call.
- Abort the turn.
- Do not inject any user message.

#### `Abort` with note
- Reject tool call.
- Do not abort the turn.
- Include the drafted note directly in the block reason so the assistant sees it in the same rejection message.

#### `Esc`
- Reject tool call.
- Abort the turn.
- Do not inject any user message.

### 9. Keep one legend across all states

The legend should not change between plain selection and inline drafting states.

### 10. Use `Esc` only in the legend

The new gate should not advertise `Ctrl+C` or `j/k`.

Reasoning:

- `Ctrl+C` is redundant and noisier than necessary.
- `j/k` can remain as undocumented convenience bindings for users who already know them, but they should not appear in the legend.

## Edge Cases

- If the selected option has an empty draft and the user presses `Enter`, it should behave like a plain `Authorize` or `Abort` selection.
- If the selected option has a non-empty draft and the user presses `Enter`, it should immediately commit that selection plus note.
- If the user switches between options repeatedly, both drafts must remain stable.
- Numeric hotkeys must be ignored while text input is active.
- `Shift+Tab` should exit inline editing without discarding the preserved draft.
- `Authorize + note` text must appear inline with the authorized tool result, not as a later asynchronous user message.
- `Abort + note` text must appear inline with the rejection reason, without aborting the turn.
- `Abort` without note must abort after rejection.
- `Esc` must not merely block the tool call; it must also call `ctx.abort()` so the assistant cannot continue.

## Rejected Alternatives

### Keep using `ctx.ui.confirm()` unchanged
Rejected because the stock implementation cannot support inline drafts or custom control flow.

### Rebuild the interaction without reference to the existing confirm implementation
Rejected. The better path is to start from the existing confirm/selector behavior and extend it so the new gate still feels native to pi.

### Spend time fixing the old permission gate or old confirm helper first
Rejected. Implementation should focus on the new gate only; the old path is being replaced.

### Separate note entry into another overlay/editor
Rejected because the user wants the interaction to stay in one pane.

### Treat drafting as a separate mode with separate controls
Rejected. The desired interaction is a lightweight inline augmentation of `Authorize`/`Abort`, not a mode switch.

### Show full preserved draft text for both options at once
Rejected in favor of compact indicators for the non-selected option. Full text for both would make the gate noisy and unstable in height.

### Make `Esc` during drafting only clear text
Rejected by user. `Esc` should always reject + abort.

### Keep `Ctrl+C` and `j/k` in the legend
Rejected to reduce noise. `j/k` may still exist as undocumented bindings.

## Integration Points

- `index.ts`
  - replace direct `ctx.ui.confirm(...)` usage with a custom gate flow
  - map gate result to one of: allow, reject+abort, allow+note-in-tool-result, reject+note-in-block-reason
  - use `ctx.abort()` for `Esc`
  - store approved notes until the matching `tool_result`, then append explanatory text to the returned content
  - embed rejected notes directly into the block reason
- `ui.ts`
  - add a dedicated permission gate component
  - derive its baseline behavior from the existing confirm/selector implementation
  - handle focus lifecycle robustly inside the new gate implementation
  - keep `/permissions` summary UI as-is unless refactoring is convenient
- `rules.ts`
  - no behavior changes required for matching, only gate presentation/execution changes
- extension runtime / agent session integration
  - `tool_result` mutation should be used for approval notes so they appear synchronously before the assistant responds
  - `tool_call` block reasons should carry rejection notes so they arrive in the same rejection message

## Implementation Plan

- [ ] Add a dedicated gate result model in `chezmoi/private_dot_pi/agent/extensions/amp-style-permission-gate/ui.ts`
- [ ] Implement a custom gate component with:
  - [ ] numbered `Authorize` / `Abort` rows
  - [ ] inline per-option drafts
  - [ ] wrapping/growing input layout
  - [ ] compact preserved-draft indicator for the non-selected option
  - [ ] one fixed legend used in all states
  - [ ] custom legend text
- [ ] Implement key handling for:
  - [ ] `Up` / `Down`
  - [ ] `Tab`
  - [ ] `Shift+Tab`
  - [ ] `Enter`
  - [ ] `Esc`
  - [ ] numeric `1` / `2` hybrid behavior
  - [ ] optional undocumented `j/k`
- [x] Replace `ctx.ui.confirm(...)` in `index.ts` with `ctx.ui.custom(...)`
- [x] Define execution outcomes for:
  - [x] plain `Authorize`
  - [x] plain `Abort`
  - [x] `Authorize + note`
  - [x] `Abort + note`
  - [x] `Esc`
- [x] Use `ctx.abort()` for the `Esc` path
- [x] Surface `Authorize + note` text by appending it to the matching `tool_result`
- [x] Ensure plain `Abort` rejects first, then aborts
- [x] Surface `Abort + note` text by embedding it in the block reason without aborting
- [x] Update legend copy to remove `Ctrl+C`, keep `j/k` undocumented, and keep the legend identical across states
- [ ] Manually verify behavior in interactive mode with at least:
  - [ ] plain `Authorize`
  - [ ] plain `Abort`
  - [ ] `Esc`
  - [ ] `Authorize + note`
  - [ ] `Abort + note`
  - [ ] switching between preserved drafts
  - [ ] wrapped long draft text
