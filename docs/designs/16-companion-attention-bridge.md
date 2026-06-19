# Companion attention bridge

## Status

Accepted

## Decision Summary

Add a generic `glimpseui:attention:*` event contract on pi's in-process `pi.events` bus so any extension can signal "this session needs user attention." The `glimpse-companion` extension acts as the sole bridge: it translates these events into its existing Unix-socket protocol and renders attention as an additive row overlay, preserving the current tool status.

The permission gate and interview tool are the first consumers. The key tradeoff is decoupling: emitters never touch the companion socket or its status vocabulary, at the cost of one extra correlation-id hop to make span resolution race-safe. Events are namespaced under `glimpseui:` to avoid bus collisions; this is a deliberate, minor naming coupling — emitters reference the namespace string but nothing else about glimpse.

## Problem Statement

The glimpse companion follows the cursor and shows per-session agent activity. When an extension blocks waiting for the user, the agent loop may be busy but the companion needs a stronger callout. The companion is click-through and follows the cursor, so it can only ever be a notification surface — but a flashing "needs you" treatment is exactly the missing signal.

We also want this to generalize: any future extension that blocks on the user should be able to raise the same callout without learning the companion's socket protocol.

## Goals

- Surface a distinct, attention-grabbing companion treatment when a session is waiting on the user.
- Keep emitters decoupled: they emit a semantic event, nothing more.
- Make the companion the single owner of the socket and of rendering decisions.
- Handle overlapping and stale spans without corrupting unrelated state.
- Degrade to a no-op when the companion is disabled or unsupported.

## Non-Goals

- Making the companion interactive. It stays click-through and notification-only.
- Cross-session or cross-process attention. The bus is per-session; the companion already multiplexes sessions by id over its socket.
- Replacing the permission gate's TUI prompt or the interview UI. The actual decision still happens in the primary UI.

## Design Decisions

### 1. Semantic `glimpseui:attention:*` events, not a glimpse-shaped passthrough

Emitters publish domain intent, not presentation. Events are namespaced under `glimpseui:` to avoid collisions on the shared bus:

```ts
pi.events.emit("glimpseui:attention:request", {
  attentionId,        // stable id for the blocking operation, often event.toolCallId
  label,              // optional short label, e.g. a permission rule label
});

pi.events.emit("glimpseui:attention:resolve", { attentionId });
```

The companion owns how attention is presented. Emitters never import glimpse, never learn the socket path, and never name a status string.

### 2. Attention annotates status instead of replacing it

Attention is additive. The companion still renders the active tool status (`Running`, `Editing`, `Done`, etc.) and sends `attention` / `attentionLabel` alongside it. This avoids save/restore edge cases and keeps the tool-state pipeline authoritative.

Consequences:

- Permission prompts can show the normal status plus the permission rule label.
- Interview prompts can glow without a label because the existing tool status is already descriptive.
- Overlapping spans only affect the attention overlay; they do not overwrite the row status.

### 3. Correlation ids make resolution race-safe

The bridge keeps a per-session map of outstanding `attentionId -> label` values:

- `glimpseui:attention:request{id,label}` — add or update the id.
- `glimpseui:attention:resolve{id}` — delete the id.
- The row is attentive while the map is non-empty.
- The displayed label is the latest non-empty outstanding label.

A resolve for an unknown or already-removed id is a no-op, so stale resolves cannot wipe an unrelated still-active attention. Overlapping spans only clear the row when the last outstanding id resolves.

### 4. Permission gate and interview emit spans

`permission-gate` wraps its blocking prompt and uses the existing tool call id as the attention id:

```ts
pi.events.emit("glimpseui:attention:request", {
  attentionId: event.toolCallId,
  label: rule.label,
});
try {
  const decision = await showPermissionGate(ctx, prompt.title, prompt.body);
} finally {
  pi.events.emit("glimpseui:attention:resolve", { attentionId: event.toolCallId });
}
```

The `finally` guarantees resolution on every branch, including reject paths that abort later.

`interview-attention` emits a span on `tool_call` for the `interview` tool and resolves it on `tool_execution_end`. It intentionally uses no label: the companion's normal tool status already names the interview.

### 5. Notification-only rendering: row pulse, dot glow, optional label

The companion does not add an `awaiting` status. It marks the affected row with:

- a neutral row pulse,
- a stronger purple dot glow,
- an optional attention label before the status,
- width/overflow handling so long command details ellipsize instead of clipping the pill.

The companion window requests a height resize from Glimpse after render so multiple rows and attention labels fit without manual height tuning.

### 6. Respect the existing enable/support gate

The bridge subscribes to `glimpseui:attention:*` unconditionally but forwards to the socket only when the companion is `enabled` and `followCursorSupport.supported` — the same guard the existing status handlers use. When disabled, the events are dropped and there is nothing user-visible to leak.

## Edge Cases & Failure Modes

- **Stale resolve:** resolve for an id not in the map is a no-op.
- **Leaked span:** the bridge clears outstanding attention on normal session lifecycle cleanup paths, so a never-resolved span cannot pin the pill forever.
- **Companion enabled mid-span:** request was dropped while disabled; the pill simply never shows for that span. Acceptable — no corrupted state.
- **Overlapping attentions on one session:** tracked by distinct ids; row attention clears only when the map is empty.
- **Reject + abort:** `finally` emits resolve before deferred abort behavior runs.
- **No subscriber:** `pi.events.emit` with no listener is a no-op.

## Rejected Alternatives

### Generic `glimpseui:status` passthrough

Have emitters emit the exact status string the companion renders. Rejected: it couples every emitter to the companion's vocabulary and socket semantics, defeating the goal of a reusable, presentation-agnostic signal.

### permission-gate writes to the companion socket directly

Skip the bus and have the gate open the socket itself. Rejected: two extensions owning the socket protocol and path, duplicated connect/spawn logic, and no reuse path for other emitters.

### Model attention as a replacement `awaiting` status

Replace the row's status with a new `awaiting` status and restore the previous status on resolve. Rejected during implementation: attention is not a tool state. Additive rendering preserves the real status, avoids snapshot/restore races, and works better with multi-session rows.

### Require UUIDs for every attention id

Force every emitter to generate `crypto.randomUUID()`. Rejected during implementation: tool call ids are already stable for permission and interview spans, and avoiding random ids removes unnecessary bookkeeping.

## Integration Points

- **`pi.events`**: in-process, per-session event bus shared by all extensions loaded in the session. Carries the `glimpseui:attention:*` contract.
- **`glimpse-companion/companion/attention.ts`**: validates request/resolve payloads and tracks outstanding attention ids.
- **`glimpse-companion/companion/session.ts`**: subscribes to attention events and includes `attention` / `attentionLabel` in companion socket messages.
- **`glimpse-companion/companion.ts`**: renders row attention, label display, overflow handling, and Glimpse resize requests.
- **`permission-gate/index.ts`**: wraps `showPermissionGate` with request/resolve emits.
- **`interview-attention.ts`**: wraps `interview` tool calls with request/resolve emits.
- Extensions are deployed via chezmoi under `chezmoi/private_dot_pi/agent/extensions/`; lint with `uv run poe lint:pi`.

## Implementation Plan

- [x] Companion attention bridge + renderer
  - Goal: Companion can render an additive attention overlay driven by `glimpseui:attention:*` events.
  - Files: `glimpse-companion/companion/attention.ts`, `glimpse-companion/companion/session.ts`, `glimpse-companion/companion.ts`.
  - Validation: `uv run poe lint:pi`; manually exercised interview and permission spans; confirmed row glow, labels, clipping fix, and resize behavior.

- [x] Permission gate emits attention spans
  - Goal: real permission prompts raise and clear the companion callout.
  - Files: `chezmoi/private_dot_pi/agent/extensions/permission-gate/index.ts`.
  - Validation: triggered a harmless permission-gated command and confirmed the callout clears.

- [x] Interview emits attention spans
  - Goal: interactive interview forms raise and clear the companion callout without changing the external interview plugin.
  - Files: `chezmoi/private_dot_pi/agent/extensions/interview-attention.ts`.
  - Validation: smoke-tested an interview; visual behavior confirmed.
