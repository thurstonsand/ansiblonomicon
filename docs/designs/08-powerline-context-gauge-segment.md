# Powerline Context Gauge Segment Plan

Status: Superseded by `chezmoi/private_dot_pi/agent/extensions/pi-powerline-footer-custom/`, which uses Pi's extension status updates instead of the old custom segment loader.

## Problem Statement

Replace the built-in `context_pct` powerline segment with a custom segment that preserves the built-in calculation logic but renders it as a fixed-width gauge instead of `icon + percent/max` text.

The new segment should:

- override the built-in by registering the same segment id: `context_pct`
- preserve the current numerator logic from `pi-powerline-footer`
- support a configurable soft cap via `maxTokens`
- change color at configurable thresholds via `warnAt` and `errorAt`
- enter an explicit over-limit state when usage exceeds the soft cap

## Design Decisions

### 1. Override strategy

Use the existing custom segment loader in `~/.pi/agent/powerline/segments/` and register a segment with id `context_pct`.

Because the segment registry resolves custom segments before built-ins, this transparently replaces the built-in segment without changing segment arrays in settings.

### 2. Preserve built-in usage calculation

The custom segment should copy the built-in calculation wholesale:

- find the last assistant message in the current session branch
- ignore assistant messages with `stopReason` of `error` or `aborted`
- compute context tokens as:
  - `input + output + cacheRead + cacheWrite`
- use the model context window as the default denominator

This keeps the segment semantically aligned with what the user already sees today.

### 3. Effective max

The gauge denominator becomes:

- `effectiveMax = contextWindow` when `maxTokens` is unset
- `effectiveMax = min(contextWindow, maxTokens)` when `maxTokens` is set

This allows a lower artificial ceiling for large-window models without ever exceeding the true model limit.

### 4. Fixed-width gauge

Use a hard-coded width to keep the segment visually stable and simple.

Recommended width: `12`

Rendered form:

- normal: `[██  15%     ]`
- over limit: `🔥[██  15%     ]`

The exact spacing can be adjusted during implementation, but the gauge should remain fixed-width across updates.

### 5. Theme-reactive coloring

Prefer Pi theme colors over hard-coded ANSI escape sequences.

The segment should color the gauge with the current Pi theme via `ctx.theme`, using theme-reactive colors that follow the active theme:

- below `warnAt` → `success`
- `warnAt` and above, below `errorAt` → `warning`
- `errorAt` and above → `error`

When over the soft cap, always use `error`.

### 6. Over-limit behavior

If `contextTokens > effectiveMax` and `effectiveMax` is coming from `maxTokens` rather than the model window:

- prepend `🔥`
- keep the segment red/error
- stop treating `maxTokens` as the denominator
- render the gauge and displayed percentage against the real model `contextWindow`

In other words, once the soft cap is exceeded, the segment behaves as though no soft cap had been specified, except for the explicit overheat indicator and forced red coloring.

Example:

- `contextWindow = 1100000`
- `maxTokens = 400000`
- `contextTokens = 460000`
- display uses `460000 / 1100000`
- display starts with `🔥`
- color is forced to red/error

## Edge Cases

### No model context window

If `contextWindow <= 0`, hide the segment rather than showing misleading output.

### Invalid thresholds or malformed settings

Use these defaults when values are omitted:

- `warnAt = 50`
- `errorAt = 80`

If either value is present but typed incorrectly, let the segment throw and fail loudly.

This design intentionally does not add compatibility shims, coercion, threshold clamping, or silent recovery paths. The settings shape should be treated as strict and fixed.

### `maxTokens <= 0`

Treat this as invalid configuration and let the segment fail loudly.

### Extremely large usage

If the computed displayed percentage exceeds 100%, cap the filled portion of the gauge at full width while still showing the numeric displayed percent.

This keeps the gauge shape stable without hiding how large usage has become.

## Rejected Alternatives

### Recompute usage from cumulative session totals

Rejected because the user wants the same calculation semantics as the current built-in segment.

### Add toggles for cache read/write inclusion

Rejected because the user does not want to manage those knobs, and preserving built-in logic is simpler and less surprising.

### Add optional icon toggles or broad fallback behavior

Rejected as unnecessary configuration and complexity. The desired settings surface is intentionally minimal: `maxTokens`, `warnAt`, `errorAt`. Only omission defaults are allowed for `warnAt` and `errorAt`; incorrect types should still fail loudly.

## Integration Points

### Custom segment location

Create the override in:

- `chezmoi/private_dot_pi/agent/powerline/segments/context_pct/index.ts`

This maps to:

- `~/.pi/agent/powerline/segments/context_pct/index.ts`

### Settings location

Update:

- `chezmoi/private_dot_pi/agent/settings.json.tmpl`

Add segment options under:

- `powerline.custom.options.context_pct`

Example:

```json
{
  "maxTokens": 400000,
  "warnAt": 50,
  "errorAt": 80
}
```

### Existing settings compatibility

Because the current config already uses `rightSegments: ["context_pct"]`, no segment list changes are required.

## Implementation Plan

- [ ] Add `context_pct` custom segment package under `chezmoi/private_dot_pi/agent/powerline/segments/context_pct/`
- [ ] Implement fixed-width gauge rendering and threshold coloring
- [ ] Copy built-in context token calculation semantics
- [ ] Apply `effectiveMax = min(contextWindow, maxTokens)` when configured
- [ ] Implement over-limit state with `🔥` and overflow percent reset
- [ ] Add `context_pct` options to `chezmoi/private_dot_pi/agent/settings.json.tmpl`
- [ ] Run `/reload` and verify appearance in normal, warning, error, and over-limit states
- [ ] Adjust spacing/width only if visual testing shows truncation or awkward alignment
