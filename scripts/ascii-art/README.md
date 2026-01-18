# ASCII Art Text Renderer

A canvas-based ASCII art rendering script that converts text to ASCII art using brightness-to-character mapping.

## Origin

This code is adapted from [alexharri/website PR#15](https://github.com/alexharri/website/pull/15), which implements a sophisticated canvas-to-ASCII rendering system for interactive web graphics.

## How It Works

1. **Canvas Rendering**: Text is rendered to an HTML5 canvas using Node.js `canvas` library at a specified font and size
2. **Cell Sampling**: The canvas is divided into a grid of cells (e.g., 1x2 or 2x4 pixels per cell)
3. **Brightness Calculation**: For each cell, the average brightness is computed using perceived luminance formula:
   ```
   brightness = (0.299 * R + 0.587 * G + 0.114 * B) / 255
   ```
4. **Character Mapping**: Brightness values (0-1) are mapped to ASCII characters sorted by visual density

## Usage

```bash
# Install dependencies
npm install

# Run the renderer
npm run render
# or
./node_modules/.bin/ts-node render-text-ascii.ts
```

## Configuration

Edit `render-text-ascii.ts` to customize:

- `TEXT` - The text to render (default: "fast jira")
- `FONT_SIZE` - Base font size in points (default: 36)
- `SCALED_FONT_SIZE` - High-res font size (default: 100)
- `FONT_FAMILY` - Font to use (default: "IBM Plex Mono")

### Character Sets

Three built-in character sets are available:

```typescript
// Detailed - 70 characters, maximum gradation
ASCII_CHARS_DETAILED = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"

// Simple - 15 characters, cleaner look
ASCII_CHARS_SIMPLE = " .,:;i1tfLCG08@"

// Blocks - 5 Unicode block characters
ASCII_CHARS_BLOCKS = " ░▒▓█"
```

### Rendering Options

```typescript
renderTextToAscii(text, fontSize, fontFamily, {
  cellWidth: 1,      // Pixels per character horizontally (smaller = more detail)
  cellHeight: 2,     // Pixels per character vertically (smaller = more detail)
  contrast: 1.2,     // Contrast enhancement (1.0 = none, >1 = more contrast)
  charset: ASCII_CHARS_DETAILED  // Character set to use
});
```

## Key Learnings

### Font Registration

Node.js `canvas` requires explicit font registration:

```typescript
import { registerFont } from "canvas";
registerFont("./fonts/IBMPlexMono-Regular.ttf", { family: "IBM Plex Mono" });
```

### Cell Aspect Ratio

Terminal characters are typically taller than wide (~2:1 ratio). Using `cellHeight: 2` with `cellWidth: 1` compensates for this, producing square-looking output in monospace terminals.

### Resolution vs Font Size

To increase ASCII art resolution:
- **Increase font size** - More pixels to sample from
- **Decrease cell size** - Finer sampling grid
- A 100pt font with 1x2 cells produces much higher detail than 36pt with 2x4 cells

### Brightness Perception

The perceived luminance formula accounts for human vision being more sensitive to green:
```
L = 0.299*R + 0.587*G + 0.114*B
```

### Contrast Enhancement

Applying gamma correction (`pow(brightness, 1/contrast)`) with contrast > 1.0 makes the ASCII art more readable by emphasizing differences between light and dark regions.

## Example Output

The script generates ASCII art like this (simplified version shown):

```
         i___,                                                 `~:       :+`
        Ud)))I                         :wi                     ]du       nd}
    .___hw___,   `>+>'      `>+<:   "__\$/___;             i_____,    i____.
    ')))od)))I  zL/(jan    Cpt)|cQ, :))x$n)))!             -)))\$)    _))X$,
        pL       ;<__X@   .bO}+l^      <$+                     ^$)       {$,
        pL     !oY{]?Y$     !](fYh?    <$+                     ^$)       {$,
     :;;bO;;:  _@/II-Q$I' lQ(i;l[W\    l@};;;`                 ^$)    ";;\$>;;.
     fxxxxxxr   I|rf]'|xl  ^]trj)I      _rxxx+                 ^$)    1xxxxxxx:
```

## Dependencies

- `canvas` - Node.js canvas implementation for server-side rendering
- `typescript` / `ts-node` - TypeScript support

## Files

- `render-text-ascii.ts` - Main rendering script
- `fast-jira-ascii.txt` - Generated output
- `fonts/IBMPlexMono-Regular.ttf` - IBM Plex Mono font (a.k.a. Blex Mono)
- `tsconfig.json` - TypeScript configuration
- `package.json` - Node.js dependencies
