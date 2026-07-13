---
name: tui-screenshot
description: Capture polished screenshots of terminal applications and TUIs. Use before terminal-control when the user wants a terminal screenshot or live TUI state documented.
---

# TUI Screenshot

Produce a **tight proof frame**: the requested state, its complete visual boundary, a small margin, the user's dark terminal background, and nothing unrelated.

Load and follow the `terminal-control` skill for launching, driving, waiting on, and saving the live terminal state. This skill owns framing and finish; Terminal Control owns interaction.

## Capture

1. Identify the exact state to prove and the final image path. Ask when either is ambiguous. Default to a tight frame; use a full viewport only when the user requests one or the surrounding application is part of the proof.
2. Launch a disposable session large enough to render the subject without clipping. Preserve the application's real configuration where useful, but disable unrelated extensions, features, or chrome that would contaminate the frame.
3. Force the application's existing dark theme even when the desktop is currently in light mode. For Pi, load/select its configured dark theme explicitly rather than relying on background detection.
4. Drive the application into the requested state. Wait for text from the **last stable row** of the finished component—not its title or another early-rendered marker—before saving. A title can appear while the rest of a modal is still being painted.
5. Save the raw PNG under `/tmp`. Keep it until the finished image has been inspected. Stop the live session after capture.

The capture step is complete when the raw image visibly contains the entire requested component and its bottom-most stable content.

## Resolve the dark background

Prefer Ghostty's configured dark theme:

1. Read `ghostty +show-config` and parse the dark branch of a paired `theme = light:...,dark:...` value.
2. Resolve its file with `ghostty +list-themes --plain --path --color=dark`.
3. Read the theme's `background` value.

If Ghostty has an explicit `background`, use it. If Ghostty is unavailable, inspect the active terminal's configuration. If the dark background cannot be determined confidently, ask the user rather than choosing generic black.

Pi and many TUIs leave the background unset so the terminal supplies it. Headless capture may render that as transparency or a near-black fallback even when foreground theme colors are correct. Normalize both cases to the resolved terminal background.

## Frame and finish

Use ImageMagick when available.

1. Inspect the raw image to locate the component's actual outer boundary. Terminal cell coordinates and displayed preview coordinates are not interchangeable; inspect source pixels or retain a deliberately generous crop.
2. Crop out unnecessary components of the TUI: editor chrome, unrelated information, loading rows, empty viewport. Preserve the complete top, side, and bottom borders if present.
3. Add a small outer margin in the resolved background color. Default to roughly 8 source pixels; consistency matters more than the exact count.
4. Flatten transparency onto the resolved background.
5. Replace only the capture backend's exact fallback background color with the resolved background. Preserve foreground colors, antialiasing, modal fills, tool-result fills, highlights, and borders.
6. Write directly to the requested project path only after the crop is correct.

Representative ImageMagick finish:

```sh
magick "$raw" \
  -crop "${width}x${height}+${x}+${y}" +repage \
  -background "$background" -alpha background -alpha off \
  -fill "$background" -opaque "$capture_fallback" \
  -bordercolor "$background" -border 8x8 \
  "$output"
```

Do not assume `#000000` is the fallback. Sample a known empty background pixel from the raw capture.

## Inspect

Display every finished image with the image-reading tool. Check all of the following:

- the requested state is unmistakable
- every outer border and corner is visible
- the margin is even and uses the terminal's dark background
- no unrelated information, empty areas, or unrelated chrome remains
- text, highlights, and fills retain the application's dark theme colors
- repeated screenshots use consistent framing and background

Re-crop or recapture until every check passes. Delete superseded variants and temporary project artifacts; `/tmp` capture sources may be removed after approval.
