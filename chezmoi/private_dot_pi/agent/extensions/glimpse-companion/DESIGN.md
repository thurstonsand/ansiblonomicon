---
name: Glimpse Companion
description: A terminal-native floating operator statusline for Pi session activity.
colors:
  pill-bg: "pi.theme.vars.bg | pi.theme.colors.userMessageBg | pi.theme.colors.customMessageBg"
  pill-border: "pi.theme.colors.border | pi.theme.vars.border"
  pill-text: "pi.theme.colors.text | pi.theme.vars.text"
  pill-muted: "pi.theme.colors.muted | pi.theme.vars.muted"
  pill-subtle: "pi.theme.colors.dim | pi.theme.vars.dim"
  pill-separator: "pi.theme.colors.dim | pi.theme.vars.dim"
  attention-dot: "pi.theme.colors.customMessageLabel | pi.theme.colors.accent"
  attention-glow: "surfaceAwareCharge(attention-dot, pill-bg)"
  attention-pulse: "rgba(pill-text, 0.10-0.12)"
  status-starting: "pi.theme.colors.muted"
  status-thinking: "pi.theme.colors.dim"
  status-responding: "pi.theme.colors.text"
  status-preparing-tool: "pi.theme.colors.dim"
  status-reading: "pi.theme.colors.mdCode"
  status-editing: "pi.theme.colors.warning"
  status-running: "pi.theme.colors.mdHeading"
  status-searching: "pi.theme.colors.accent"
  status-done: "pi.theme.colors.success"
  status-error: "pi.theme.colors.error"
typography:
  label:
    fontFamily: "BerkeleyMono Nerd Font Mono, Menlo, Monaco, ui-monospace, SF Mono, monospace"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.2
  meta:
    fontFamily: "BerkeleyMono Nerd Font Mono, Menlo, Monaco, ui-monospace, SF Mono, monospace"
    fontSize: "10px"
    fontWeight: 500
    lineHeight: 1.2
rounded:
  pill: "8px"
  row: "2px"
  dot: "999px"
spacing:
  row-x: "10px"
  row-y: "4px"
  gap: "6px"
components:
  companion-pill:
    backgroundColor: "{colors.pill-bg}"
    textColor: "{colors.pill-text}"
    rounded: "{rounded.pill}"
  session-row:
    typography: "{typography.label}"
    rounded: "{rounded.row}"
    padding: "{spacing.row-y} {spacing.row-x}"
---

# Design System: Glimpse Companion

## 1. Overview

Creative North Star: **Operator Statusline**.

The Glimpse Companion is a floating statusline for Pi sessions: compact like terminal chrome, readable like an operator panel, and restrained enough to live in peripheral vision. It borrows the density and immediacy of a statusline, but adapts it into a small HUD that can float above any window.

The companion should feel terminal-native rather than macOS-native. It derives its color system from Pi themes, uses monospace typography, and avoids dashboard structure. Its job is to expose session identity and state, not to become a monitoring app.

**Key Characteristics:**

- Theme-native surface and state colors.
- Compact row rhythm with high information density.
- Folder/project identity as the strongest text anchor.
- Attention states that are visible without becoming decorative alerts.
- Stable layout behavior that avoids peripheral jitter.

## 2. Colors

The palette is semantic and theme-derived. Frontmatter color values are pointers to the Pi theme roles and companion derivations that define the design. Concrete hex values are implementation fallbacks only; they are not the design source of truth.

### Primary

- **Theme Surface** (`pillBg`): The mostly opaque glass surface for the pill. Dark themes use dark glass; light themes use paper glass. The surface should remain readable over arbitrary windows, not just terminal backgrounds.
- **Theme Text** (`text`, `muted`, `subtle`): Project names use the strongest readable text. Status, detail, and metadata step down through muted and subtle variants.

### Secondary

- **Status Dots** (`dots`): Status colors map to Pi theme semantics: success, warning, accent/link, heading/code, and error roles. They should change with the active theme rather than forming a separate companion palette.

### Tertiary

- **Attention Color** (`attentionDot`, `attentionGlow`, `attentionPulse`): Attention is additive. It should highlight the existing session row without replacing the row's status. The dot carries the strongest color; the row pulse carries state over area.

### Neutral

- **Border and Divider** (`border`, `divider`): Borders and dividers separate the floating surface and rows without creating dashboard chrome.
- **Separator** (`separator`): Inline separators should be low-contrast punctuation, not visual landmarks.

### Color Rules

**The Theme-Native Rule.** Do not introduce a standalone companion brand palette unless the active Pi theme cannot provide a readable color. And even then, do so only with the explicit approval from the user.

**The Area Belongs to State Rule.** Dot glow is an accent. Row or pill dimming/pulsing is state.

## 3. Typography

**Display Font:** BerkeleyMono Nerd Font Mono  
**Body Font:** BerkeleyMono Nerd Font Mono, then Menlo, Monaco, ui-monospace, SF Mono, monospace  
**Label/Mono Font:** same monospace stack

**Character:** Compact terminal telemetry. Text should feel like a statusline, not app copy.

### Hierarchy

- **Title / Project** (500, 11px): The folder or project name. This is the primary label and must remain readable before any other text.
- **Status** (600, 11px): The active state label, such as Running or Thinking. Useful, but secondary to project identity.
- **Detail** (600, 10px): Tool command, file name, or short activity detail. Truncates first when space is tight.
- **Meta** (500, 10px): Context percentage and elapsed time. Quiet, useful telemetry.

### Typography Rules

**The Folder-First Rule.** Preserve project/folder readability before preserving detail, metadata, or status verbosity.

## 4. Elevation

The companion uses theme glass: a mostly opaque theme-derived surface with light blur and a Tailwind-derived shadow. Because it floats above all windows, not only terminal windows, elevation must separate it from unknown backgrounds while avoiding heavy app chrome.

### Shadow Vocabulary

- **Floating HUD Shadow** (`0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)`): The Tailwind `shadow-xl` recipe, copied directly for a familiar floating separation. Used on the outer pill only. Rows should not cast their own shadows.
- **Backdrop Blur** (`blur(12px)`): Used on the pill surface to integrate with varied backgrounds. The surface remains mostly opaque so contrast does not depend on blur.

### Elevation Rules

**The One Floating Surface Rule.** Elevation belongs to the outer pill. Internal rows use color, divider, and motion, not nested shadows.

## 5. Components

### Companion Pill

The pill is the single floating HUD container.

- **Shape:** Rounded outer corners (`8px`) with clipped overflow.
- **Background:** Theme-derived dark glass or paper glass at high opacity.
- **Border:** Theme-derived border or readable text-derived fallback.
- **Shadow:** Subtle floating HUD shadow only on the pill.
- **Behavior:** Fades out when no sessions are present and resizes to fit content.

### Session Rows

Rows are compact statusline segments inside the pill.

- **Shape:** Mostly square internal row corners, with outer rows aligning visually to the pill edge.
- **Content:** Dot, project, optional attention label, status, detail, then metadata below.
- **State:** Status changes may update color and text, but should avoid unnecessary reordering or animation resets.
- **Priority:** Important rows may become easier to see, but priority should not add headers or dashboard panels by default.

### Status Dots

Dots are small semantic state anchors.

- **Size:** 5px circular dot.
- **Color:** Theme semantic status color.
- **Attention:** Attention may override dot color and add a small glow, but the glow should remain tight.

### Overflow Row

Overflow is a compact summary, not a second surface.

- **Style:** Same density and typography as session rows.
- **Copy:** Prefer semantic counts when useful, such as `+2 need attention · +2 active`.
- **Attention:** Pulse only when hidden attention exists.

### Attention State

Attention is an overlay on session state, not a replacement for session state.

- **Dot:** Strong attention color with tight glow.
- **Row:** Subtle area pulse indicating the session needs action.
- **Label:** Optional short text label when the source of attention is meaningful.
- **Motion:** Pulse should be phase-stable across unrelated updates.

## 6. Do's and Don'ts

### Do

- Derive colors from the active Pi theme.
- Keep the companion compact enough for peripheral use.
- Preserve project/folder labels as the primary readable text.
- Use attention treatment to clarify urgency without adding dashboard structure.
- Keep row ordering stable unless priority state changes.
- Make the floating surface readable over arbitrary window backgrounds.

### Don't

- Do not make the companion feel like macOS notification chrome.
- Do not turn it into a dashboard or monitoring panel.
- Do not rely on color alone for attention or status.
- Do not allow ordinary status churn to reshuffle rows or restart visible motion.
- Do not let glass/transparency reduce contrast below readable levels.
- Do not add headers, badges, or extra panels when ordering and state treatment are enough.
