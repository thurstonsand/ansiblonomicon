# Pin Model

## Status

Accepted

## Decision Summary

Add a local Pi extension (`pin-model/index.ts`) that makes model switching session-scoped: it silently restores the pinned default model, provider, and thinking level in `settings.json` after every switch, and adds a `/pin-model` command as the deliberate way to change the pinned default from within Pi. The pin itself lives as a custom `pinnedModel` key inside `settings.json`, shared by all sessions. The tradeoff is a write-then-undo dance against Pi's own persistence (a timing heuristic) in exchange for zero changes to built-in switching UX and no Pi fork.

## Problem Statement

Every model-switch path in Pi — `/model`, the Ctrl+L selector, Ctrl+P cycling — calls `AgentSession.setModel` (or the cycle equivalents), which unconditionally persists `defaultProvider`/`defaultModel` to `~/.pi/agent/settings.json` via `setDefaultModelAndProvider()`. Thinking-level changes (Shift+Tab, and the clamping that happens on model switches) persist `defaultThinkingLevel` the same way. There is no session-scoped model setter, in the UI or in the extension API (`pi.setModel` routes through the same persisting path).

Consequence: switching to Sonnet mid-session to handle one task rewrites the default, and every subsequent new session starts on Sonnet. Since `settings.json` is generated from chezmoi (`chezmoi/private_dot_pi/agent/settings.json.tmpl`), this also creates permanent drift between the live file and the chezmoi source. The desired behavior: the default is stable across new sessions; in-session switches are temporary.

Verified against Pi v0.80.6 source (`packages/coding-agent/src/core/agent-session.ts`, `settings-manager.ts`).

## Goals

- In-session model and thinking-level switches never durably change the defaults new sessions start with.
- All built-in switching UX (`/model`, Ctrl+L, Ctrl+P, Shift+Tab) keeps working unmodified.
- A deliberate, low-friction way to change the pinned default from within Pi (`/pin-model`).
- Reduce drift against the chezmoi-managed `settings.json`.

## Non-Goals

- No override or rebinding of built-in keybinds or the `/model` command.
- No custom model-cycling logic.
- No upstream Pi change (a `persistModelSelection: false` setting would be the proper fix; out of scope).
- No improvement over `/model`'s matching semantics for `/pin-model <pattern>` — exact parity, suboptimal though it is. Enhancement deferred.
- No separate pin file; the pin lives in `settings.json` itself.

## Exposed Shape

### `/pin-model` command

- `/pin-model` (no argument): pins the current session's model + thinking level as the new default — writes `pinnedModel` and the three default fields to `settings.json` immediately. Notifies in the style of `/model` (`Model: <id>`).
- `/pin-model <pattern>`: argument autocomplete over `provider/id` references via `getArgumentCompletions`. Resolves the pattern with `/model`'s exact-match semantics (`provider/id` or unique bare `id`). On an exact match: switches the session to that model via `pi.setModel` **and** pins it. On no exact match: shows a `ctx.ui` picker of partial matches (the extension analog of `/model`'s prefiltered selector); the chosen model is switched to and pinned. No matches: error notify.

### settings.json boundary

- The extension owns one custom key, `pinnedModel: { provider, modelId, thinkingLevel }`, and rewrites three Pi-owned fields: `defaultProvider`, `defaultModel`, `defaultThinkingLevel`. All other content is preserved via read-modify-write. Verified against Pi v0.80.6: `migrateSettings` only rewrites specific legacy keys and `persistScopedSettings` spreads current file contents before applying modified fields, so the unknown `pinnedModel` key survives every Pi write.
- Writes take the same `proper-lockfile` lock Pi uses (`settings.json` path, `realpath: false`), so concurrent sessions and Pi's own write queue cannot corrupt the file.
- Restores are silent; only `/pin-model` produces user-visible output.

### Pi extension events consumed

- `model_select`, `thinking_level_select`: schedule a restore verify-loop.
- `session_shutdown`: final restore backstop.

## Design Decisions

### 1. Restore-only, not a parallel switching mechanism

The key enabler in `SettingsManager`: `save()` persists only fields marked modified and clears the marks after each write. Once Pi's model-switch write lands, nothing re-persists the switched model later — so an external restore of the file is durable. A restore-only extension therefore converts _every_ built-in switch path into session-scoped behavior with no custom cycling and no keybind changes. Alternatives (custom cycle keybind, unbinding Ctrl+P) were rejected as more surface for no gain.

### 2. Pin source: `pinnedModel` key resident in settings.json

The pin is a `pinnedModel` object stored in `settings.json` alongside the defaults it protects. Every restore tick reads it fresh from the file, so it is shared across concurrent sessions and survives crashes. Bootstrap: if the key is absent at extension load, it is initialized from the current default fields.

This replaced an earlier in-memory-snapshot decision, which had two failure modes: a session crashing between switch and restore poisons the next session's snapshot, and a stale snapshot in session A clobbers a pin freshly set by session B. File residency eliminates both. The prerequisite was verifying that Pi preserves unknown settings keys (see Exposed Shape).

### 3. Verify-loop restore timing

Pi persists via an async write queue; `model_select` may be emitted before the queued write lands. An immediate restore could be clobbered. Instead, each switch event schedules idempotent check-and-restore ticks at ~300ms / 1s / 3s after the last event (new events reset the timers, so spamming Ctrl+P defers restores rather than stacking them): lock → read → compare defaults to the file-resident pin → rewrite if drifted. Later ticks are no-ops once the restore sticks. `session_shutdown` performs a final restore. This is a heuristic, not a proof — accepted because ticks are cheap and the shutdown backstop covers stragglers.

### 4. Thinking level is pinned together with the model

Model switches clamp and persist `defaultThinkingLevel`; Shift+Tab persists it too. Pinning only the model would leave the thinking level drifting through the same hole.

### 5. `/pin-model <pattern>` matches with exact `/model` parity

Pi's exact matcher (`findExactModelReferenceMatch`) is not exported at the package root and the `exports` map blocks deep imports, so its ~50-line logic is reimplemented verbatim: exact `provider/id`, ambiguity rejection, unique bare-`id` match. Its quirks are inherited knowingly (e.g. `anthropic/haiku` fails while bare `haiku` could match via nothing — both simply fall to the picker). Consistency with `/model` was chosen over a smarter matcher; a provider-aware substring matcher was designed and deferred.

### 6. Model candidates come from `ctx.modelRegistry.getAvailable()`

`/model` prefers `--models`-scoped models when present; the extension API does not expose scoped models, so the registry's available list is used. Acceptable divergence for a personal setup that does not use `--models`.

## Edge Cases & Failure Modes

- **Session crashes after a switch, before restore:** the default fields stay drifted until any session's next restore tick, `/pin-model`, or extension load notices the mismatch against `pinnedModel` and heals it. The pin itself cannot be poisoned.
- **Two live sessions, one switches models:** the switching session restores the file; the other session's in-memory state is untouched. Its own future saves cannot resurrect the switched model (modified-marks already cleared).
- **`/pin-model` in session A, then session B switches models:** B's restore tick reads the pin from the file and restores to A's new pin. No clobbering.
- **User hand-edits or chezmoi re-applies settings.json without `pinnedModel`:** extension re-initializes the pin from the default fields on next load; mid-session ticks treat a missing key the same way.
- **Session resume emits `model_select` with `source: "restore"`:** treated like any switch — verify-loop runs, default stays pinned.
- **Lock contention:** `proper-lockfile` `lockSync` with retry, same protocol as Pi; a failed acquisition skips that tick (a later tick or shutdown retries).
- **settings.json unparseable at a tick:** skip the tick; never write a file we could not parse.

## Alternatives

### Upstream `persistModelSelection` setting in Pi

- **Status:** Open
- **Open Issue:** The write-then-undo dance exists only because Pi conflates "current model" with "default model."
- **Discussion:** The clean fix is a Pi setting that makes model selection session-scoped. This extension is the local workaround.
- **Next step:** Propose upstream; if accepted, this extension reduces to `/pin-model` conveniences or is deleted.

### In-memory pin snapshot at extension load

- **Status:** Rejected
- **Decision:** Originally chosen for simplicity with the crash-drift risk accepted. Rejected once the cross-session clobbering scenario surfaced (stale snapshot in one session overwrites a pin freshly set in another) and the file-resident key was verified safe against Pi's settings migration and merge behavior.

### Dedicated chezmoi-templated pin file

- **Status:** Rejected
- **Decision:** Immune to crash-drift poisoning, but adds a second config artifact to keep in sync with `settings.json.tmpl`. The file-resident `pinnedModel` key achieves the same immunity inside the existing artifact.

### Custom cycle keybind with Ctrl+P unbound

- **Status:** Rejected
- **Decision:** More surface (keybindings.json remap, custom cycle logic) and worse UX than keeping the built-ins working and undoing their persistence.

### Provider-aware substring matching for `/pin-model <pattern>`

- **Status:** Deferred
- **Discussion:** `provider/substring` matching (e.g. `anthropic/haiku` → `claude-haiku-4-5`) would fix a real asymmetry in Pi's matchers, but diverges from `/model` semantics. Consistency wins for now; revisit if the built-in is ever overridden.

## Implementation Plan

- [ ] Phase 1: Restore engine
  - Goal: Model/thinking switches stop durably changing settings.json defaults.
  - Files: `chezmoi/private_dot_pi/agent/extensions/pin-model/index.ts`, `package.json`, `package-lock.json`, `tsconfig.json`, `pin-model.test.ts`
  - Work: Extension factory reads `settings.json`, initializes `pinnedModel` from the default fields if absent; implement locked read-modify-write restore that reads the file-resident pin and rewrites the three default fields; wire `model_select`/`thinking_level_select` to the ~300ms/1s/3s verify-loop (timer reset on new events); `session_shutdown` backstop restore.
  - Validation: `scripts/pi-lint.sh` (or repo lint entry) passes; smoke test — start pi, Ctrl+P to another model, confirm `settings.json` reverts within ~3s while footer still shows the switched model; new session starts on the pinned default; Shift+Tab thinking change reverts likewise.

- [ ] Phase 2: `/pin-model` command
  - Goal: Deliberate re-pinning from within Pi.
  - Files: `chezmoi/private_dot_pi/agent/extensions/pin-model/index.ts`
  - Work: Register `pin-model` command with `getArgumentCompletions` offering `provider/id` references from `ctx.modelRegistry.getAvailable()`. No-arg: write pin from current session state, write immediately, notify `Model: <id>`. With pattern: reimplement `findExactModelReferenceMatch` semantics over the same candidates; exact hit → `pi.setModel` + pin; otherwise `ctx.ui` picker over partial matches → switch + pin; zero matches → error notify.
  - Validation addendum: completions appear when typing `/pin-model`; concurrent-session test — pin in one session, switch models in another, confirm the file converges on the new pin.
  - Validation: Smoke test — `/pin-model` after a Ctrl+P switch makes the switched model the durable default (survives new session); `/pin-model <provider/id>` switches and pins; ambiguous pattern opens picker; garbage pattern errors.

- [ ] Phase 3: chezmoi integration check
  - Goal: Deployed state matches the repo and drift is understood.
  - Files: `chezmoi/private_dot_pi/agent/settings.json.tmpl`
  - Work: Seed `pinnedModel` alongside the host-aware default fields; `chezmoi apply` (or diff) confirms the extension deploys; note in the commit message that live `settings.json` drift for default model now self-heals.
  - Validation: `chezmoi diff` clean for the extensions dir after apply; fresh pi session loads the extension without errors.
