---
name: tui-screenshot
description: Capture polished screenshots of terminal applications and TUIs. Use before tuistory when the user wants a terminal screenshot or live TUI state documented.
---

# TUI Screenshot

Produce a **tight proof frame**: the requested state, its complete visual boundary, a small margin, and nothing unrelated.

Load and follow the `tuistory` skill for launching, driving, waiting on, and saving the live terminal state. This skill owns framing and finish; Tuistory owns interaction.

In Amp orbs, run Tuistory through Bun so screenshots do not use the incompatible Node renderer. Replace every bare `tuistory` invocation from the Tuistory skill with `bunx --bun tuistory`.

## Capture

1. Identify the exact state to prove and the final image path. Ask when either is ambiguous. Default to a tight frame; use a full viewport only when the user requests one or the surrounding application is part of the proof.
2. Launch a disposable session large enough to render the subject without clipping. Preserve the application's real configuration where useful, but disable unrelated extensions, features, or chrome that would contaminate the frame.
3. Force the application into the requested light or dark theme rather than relying on terminal background detection. For Pi, load/select the matching configured theme explicitly.
4. Drive the application into the requested state. Wait for text from the **last stable row** of the finished component, not its title or another early-rendered marker, before saving. A title can appear while the rest of a modal is still being painted.
5. Inspect `snapshot --trim`, then save the raw PNG under `/tmp`. Keep it until the finished image has been inspected. Stop the disposable live session after capture.

The capture step is complete when the raw image visibly contains the entire requested component and its bottom-most stable content.

## Theme

Use Gruvbox Hard explicitly when rendering the screenshot:

- Dark: `--background '#1d2021' --foreground '#ebdbb2' --frame-color '#1d2021'`
- Light: `--background '#f9f5d7' --foreground '#3c3836' --frame-color '#f9f5d7'`

Default to dark unless the user requests light or the requested state specifically concerns light mode. Always pass `--pixel-ratio 2` and an explicit output path.

Tuistory's foreground and background options supply terminal defaults; they do not recolor ANSI colors emitted by the application. Configure the application itself for Gruvbox when it supports themes.

## Frame and finish

Use ImageMagick when available.

1. Inspect the raw image to locate the component's actual outer boundary. Terminal cell coordinates and displayed preview coordinates are not interchangeable; inspect source pixels or retain a deliberately generous crop.
2. Crop out unnecessary components of the TUI: editor chrome, unrelated information, loading rows, empty viewport. Preserve the complete top, side, and bottom borders if present.
3. Add a small outer margin in the selected Gruvbox background color. Default to roughly 8 source pixels; consistency matters more than the exact count.
4. Flatten transparency onto the selected background.
5. Preserve foreground colors, antialiasing, modal fills, tool-result fills, highlights, and borders.
6. Write directly to the requested project path only after the crop is correct.

Representative ImageMagick finish:

```sh
magick "$raw" \
  -crop "${width}x${height}+${x}+${y}" +repage \
  -background "$background" -alpha background -alpha off \
  -bordercolor "$background" -border 8x8 \
  "$output"
```

## Inspect

Display every finished image with the image-reading tool. Check all of the following:

- the requested state is unmistakable
- every outer border and corner is visible
- the margin is even and uses the selected Gruvbox background
- no unrelated information, empty areas, or unrelated chrome remains
- text, highlights, and fills retain the application's theme colors
- repeated screenshots use consistent framing and background

Re-crop or recapture until every check passes. Delete superseded variants and temporary project artifacts; `/tmp` capture sources may be removed after approval.
