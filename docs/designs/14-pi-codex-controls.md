# Pi Codex Controls

## Status

Accepted

## Decision Summary

Replace the broad `@howaboua/pi-codex-conversion` package with a small local Pi extension that only controls Codex request options and exposes a `/codex` settings panel. The extension deliberately avoids provider replacement, custom tools, skills discovery, prompt rewrites, native compaction, native image/web handling, and Pi-native tool changes. The tradeoff is losing the conversion package's extra features in exchange for predictable, Pi-native behavior.

## Problem Statement

The existing Codex conversion extension performs too many unrelated integrations: provider adaptation, custom tool registration, skills discovery, request rewriting, compaction support, status UI, and native media/web handling. Only a narrow subset is wanted: fast-mode priority requests, text verbosity control, reasoning summary control, and a `/codex` UI that writes shared settings for the statusline extension to display.

## Goals

- Replace `@howaboua/pi-codex-conversion` with a focused local extension managed from this repository.
- Store Codex controls in the main Pi `settings.json` under a top-level `codex` object.
- Provide `/codex` commands and an interactive status/settings panel in the style of `/title` from `pi-sessions`.
- Mutate only the outgoing OpenAI Codex Responses payload fields needed for fast mode, verbosity, and reasoning summary.
- Update the statusline integration in the same implementation pass so it reads the new `settings.codex` values.

## Non-Goals

- No custom provider registration.
- No custom tool registration or Pi-native tool replacement.
- No skill discovery or prompt injection.
- No native Codex compaction implementation.
- No native image generation or native web search integration.
- No support for `service_tier=flex`, `default`, `auto`, or `scale` in the first implementation.
- No statusline toggle in `/codex`; statusline behavior remains owned by the statusline extension.

## Design Decisions

### 1. Local extension name

Use `pi-codexctl` for the package/extension and reserve `/codex` for the command. The name is blunt and Unix-like: it controls Codex behavior without implying a broader framework or provider replacement.

### 2. Main settings file owns the state

Store settings in Pi's main settings file:

```json
{
  "codex": {
    "fast": false,
    "verbosity": "low",
    "reasoningSummary": "auto"
  }
}
```

This matches the `pi-sessions` pattern of reading nested extension-owned settings from the root Pi settings object. It also gives the statusline extension a stable shared source of truth. Pi core does not need to understand the `codex` key.

### 3. Fast mode is priority-only for now

`fast: true` injects:

```json
{ "service_tier": "priority" }
```

`fast: false` omits `service_tier`. Although OpenAI's API enum includes `auto`, `default`, `flex`, `scale`, and `priority`, only priority is needed now. Flex/default/auto can be added later if their real behavior is useful enough to expose.

### 4. Verbosity maps directly to Responses text verbosity

`verbosity` supports:

```text
low → medium → high
```

The request mutator ensures `payload.text` exists and sets:

```json
{ "text": { "verbosity": "low|medium|high" } }
```

Pi's Codex Responses provider already defaults verbosity to `low`; persisting it explicitly makes the status panel and statusline deterministic.

### 5. Reasoning summary is controlled only when reasoning exists

`reasoningSummary` supports:

```text
auto → concise → detailed → off
```

The mutator sets `payload.reasoning.summary` only if `payload.reasoning` already exists. It must not create a `reasoning` object by itself, because that could accidentally enable reasoning for a request where Pi intentionally disabled it.

### 6. `/codex` is both status and control surface

`/codex` with no arguments opens an interactive panel. There is no separate `/codex status` command unless implementation discovers it is useful for non-interactive scripting; the panel is the status surface.

The panel should follow the style of the `/title` menu from `pi-sessions`: a focused transient UI, concise status rows, direct single-key actions, and Esc/quit behavior that returns cleanly to the main Pi session. It should feel like a sibling Pi control panel, not a separate mini-application.

Supported commands:

```text
/codex
/codex fast on
/codex fast off
/codex verbosity low|medium|high
/codex summary auto|concise|detailed|off
```

Panel keybindings:

```text
f  toggle fast
v  cycle verbosity: low → medium → high
s  cycle summary: auto → concise → detailed → off
q  close
Esc close
```

### 7. Provider request mutation is intentionally narrow

The `before_provider_request` handler applies only to the OpenAI Codex provider path. It should not affect normal `openai` models or other Responses providers in the first version.

Expected mutation:

```ts
if (config.fast) {
  payload.service_tier = "priority";
}

payload.text = { ...(isObject(payload.text) ? payload.text : {}), verbosity: config.verbosity };

if (isObject(payload.reasoning)) {
  payload.reasoning = { ...payload.reasoning, summary: config.reasoningSummary };
}
```

This should closely mirror the existing conversion extension's `applyCodexRequestParams` approach: return a shallow-copied payload with conditional spread fields rather than aggressively normalizing the whole request. In particular, when `fast` is false, leave any existing `service_tier` untouched instead of proactively deleting it.

### 8. Statusline reads the same settings

The statusline extension should stop depending on `pi-codex-conversion` settings or status text. It should read `settings.codex` and render the new values directly. `/codex` does not own a statusline visibility toggle.

## Edge Cases & Failure Modes

- **Unknown or missing `settings.codex`:** use defaults `{ fast: false, verbosity: "low", reasoningSummary: "auto" }`.
- **Invalid setting values:** ignore invalid values and fall back to defaults for that field. Do not crash Pi startup over a typo.
- **Payload is not an object:** return the payload unchanged.
- **Payload has no `text`:** create `text` to set verbosity.
- **Payload has no `reasoning`:** do not set reasoning summary.
- **Non-Codex provider request:** leave payload unchanged.
- **Old conversion package still installed:** `/codex` command conflicts are likely. Replacement must remove `npm:@howaboua/pi-codex-conversion` from settings before enabling the new extension.
- **Priority unavailable or downgraded:** OpenAI may return a different actual service tier. The extension only requests priority; it does not promise priority was honored.

## Rejected Alternatives

### Keep `@howaboua/pi-codex-conversion` with `applyPatchOnly`

Rejected because `applyPatchOnly` disables most desired request rewriting while leaving unwanted package behavior installed, including custom command/provider/tool surface area and skills discovery behavior.

### Expose full `service_tier` selection now

Rejected for the first version. OpenAI documents multiple values, but the currently useful behavior is priority fast mode. A broader tier selector can be added later if flex/default/auto prove operationally valuable.

### Implement Codex-native compaction now

Rejected as too heavy for this pass. It would require deeper integration with Pi's compaction path and Codex encrypted reasoning/context behavior. The current goal is request option control, not context lifecycle management.

### Register or replace tools

Rejected. Pi's native tools should remain native. Tool modification was the main reason to remove the existing conversion package.

## Integration Points

- `chezmoi/private_dot_pi/agent/settings.json.tmpl`: remove the conversion package, add the local replacement package/extension, and seed `codex` defaults.
- `chezmoi/private_dot_pi/agent/extensions/`: likely home for the local extension source and package metadata, following the existing managed extension pattern.
- `pi-sessions`: reference implementation for `/title` command parsing and interactive panel style.
- `pi-powerline-footer`: statusline integration must read `settings.codex` after this change.
- Pi extension API: use `registerCommand` and `before_provider_request`; do not register providers or tools.
- Pi `SettingsManager`: read root settings like `pi-sessions`; write updates to main settings using the same settings-file approach.

## Implementation Plan

- [x] Phase 1: Add local Codex controls extension skeleton
  - Goal: Introduce a focused extension with defaults and settings read/write helpers, but do not yet replace the installed conversion package.
  - Files: `chezmoi/private_dot_pi/agent/extensions/`, package metadata if needed, TypeScript config as needed.
  - Work: Create extension entrypoint, config schema/defaults, settings load/save helpers modeled after `pi-sessions`, and unit-testable pure helpers for cycling values.
  - Validation: `uv run poe lint:pi` or targeted TypeScript/Biome checks for the extension package.

- [x] Phase 2: Implement request mutation
  - Goal: Apply only the agreed Codex request options.
  - Files: new extension source under `chezmoi/private_dot_pi/agent/extensions/`.
  - Work: Add `before_provider_request` handler scoped to OpenAI Codex; inject priority service tier for fast mode, text verbosity, and reasoning summary only when `payload.reasoning` exists.
  - Validation: Unit tests for object/non-object payloads, missing text, missing reasoning, invalid config, fast on/off, and non-Codex no-op behavior.

- [x] Phase 3: Implement `/codex` commands and panel
  - Goal: Provide the interactive and command-line control surface.
  - Files: new `/codex` command modules and panel component under the extension source.
  - Work: Register `/codex`; implement command parsing for `fast on|off`, `verbosity`, and `summary`; implement panel with `f`, `v`, `s`, `q`, and Esc behavior in the style of `/title`.
  - Validation: Command parser tests plus manual Pi smoke test for panel rendering and settings writes.

- [x] Phase 4: Replace conversion package in managed settings
  - Goal: Switch managed Pi config from conversion package to the new local extension.
  - Files: `chezmoi/private_dot_pi/agent/settings.json.tmpl`, possibly `chezmoi/private_dot_pi/agent/pi-codex-conversion.json.tmpl`.
  - Work: Remove `npm:@howaboua/pi-codex-conversion`; add the local extension/package path; add default `codex` settings; remove or stop deploying the old conversion config.
  - Validation: Render/apply chezmoi preview with `uv run poe cz-diff`; verify generated settings contain one `/codex` provider and no old conversion package.

- [x] Phase 5: Update statusline integration
  - Goal: Make the statusline display the new Codex settings source.
  - Files: local `pi-powerline-footer` source or this repo's managed statusline config, depending on where the current segment is implemented.
  - Work: Replace reads of conversion settings/status text with `settings.codex`; render fast, verbosity, and summary consistently; keep statusline visibility/configuration owned by the statusline extension.
  - Validation: Existing statusline tests if present, targeted TypeScript check, and manual Pi smoke test.

- [x] Phase 6: End-to-end validation and cleanup
  - Goal: Prove the replacement works and leaves no old behavior active.
  - Files: final cleanup across settings/templates/docs.
  - Work: Run lint/type checks; start Pi with Codex model; verify `/codex` opens; toggle each field; confirm `settings.json` updates; confirm outgoing payload mutation through logging or a controlled test hook; confirm no custom Codex conversion tools/provider are registered.
  - Validation: `uv run poe lint:pi`, relevant statusline checks, `uv run poe cz-diff`, and manual smoke test in Pi.

## Unexpected Behavior

- The existing custom footer watcher only marks the model display dirty when the watched settings file changes. Immediate redraw from the file watcher would require retaining an ambient `ExtensionContext`, so the implementation keeps the safer dirty-flag behavior and refreshes on the next normal Pi event or `/custom-footer-refresh`.
- `uv run poe pi:update-deps` initially failed because the dependency update script resolved the `pi` executable through the mise shim, then looked for `package.json` next to the mise binary. The script now asks mise for the real `pi` binary path when available before deriving the installed Pi package version.
