// Script to render text as ASCII art using the character vector matching system

import { createCanvas, registerFont } from "canvas";
import * as path from "path";
import * as fs from "fs";

// Configuration
const TEXT = "fast jira";
const FONT_SIZE = 36;
const FONT_FAMILY = "IBM Plex Mono";
const FONT_PATH = path.resolve(__dirname, "./fonts/IBMPlexMono-Regular.ttf");

// ASCII characters sorted roughly by visual density (light to dark)
const ASCII_CHARS_SIMPLE = " .,:;i1tfLCG08@";
const ASCII_CHARS_BLOCKS = " ░▒▓█";
const ASCII_CHARS_DETAILED = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$";

// Register the font
registerFont(FONT_PATH, { family: FONT_FAMILY });

function renderTextToAscii(
  text: string,
  fontSize: number,
  fontFamily: string,
  options: {
    cellWidth?: number;
    cellHeight?: number;
    contrast?: number;
    charset?: string;
  } = {}
): string {
  const {
    cellWidth = 2,
    cellHeight = 4,
    contrast = 1.0,
    charset = ASCII_CHARS_DETAILED,
  } = options;

  // Create a canvas to measure the text
  const measureCanvas = createCanvas(1, 1);
  const measureCtx = measureCanvas.getContext("2d");
  measureCtx.font = `${fontSize}px ${fontFamily}`;
  const metrics = measureCtx.measureText(text);

  // Calculate canvas dimensions with padding
  const padding = fontSize * 0.2;
  const canvasWidth = Math.ceil(metrics.width + padding * 2);
  const canvasHeight = Math.ceil(fontSize * 1.4 + padding * 2);

  // Create the main canvas
  const canvas = createCanvas(canvasWidth, canvasHeight);
  const ctx = canvas.getContext("2d");

  // Fill with black background
  ctx.fillStyle = "black";
  ctx.fillRect(0, 0, canvasWidth, canvasHeight);

  // Draw text in white
  ctx.fillStyle = "white";
  ctx.font = `${fontSize}px ${fontFamily}`;
  ctx.textBaseline = "middle";
  ctx.fillText(text, padding, canvasHeight / 2);

  // Get image data
  const imageData = ctx.getImageData(0, 0, canvasWidth, canvasHeight);
  const data = imageData.data;

  // Calculate grid dimensions
  const cols = Math.floor(canvasWidth / cellWidth);
  const rows = Math.floor(canvasHeight / cellHeight);

  // Convert to ASCII
  let asciiArt = "";

  for (let row = 0; row < rows; row++) {
    let line = "";
    for (let col = 0; col < cols; col++) {
      let totalBrightness = 0;
      let pixelCount = 0;

      const startX = col * cellWidth;
      const startY = row * cellHeight;

      for (let y = startY; y < Math.min(startY + cellHeight, canvasHeight); y++) {
        for (let x = startX; x < Math.min(startX + cellWidth, canvasWidth); x++) {
          const idx = (y * canvasWidth + x) * 4;
          const r = data[idx];
          const g = data[idx + 1];
          const b = data[idx + 2];
          const brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
          totalBrightness += brightness;
          pixelCount++;
        }
      }

      let avgBrightness = pixelCount > 0 ? totalBrightness / pixelCount : 0;

      // Apply contrast
      if (contrast !== 1.0) {
        avgBrightness = Math.pow(avgBrightness, 1 / contrast);
        avgBrightness = Math.min(1, Math.max(0, avgBrightness));
      }

      const charIndex = Math.floor(avgBrightness * (charset.length - 1));
      line += charset[charIndex];
    }
    // Trim trailing spaces from each line
    asciiArt += line.trimEnd() + "\n";
  }

  return asciiArt;
}

// Main execution - High resolution render at 100pt with 1x2 cell sampling
const SCALED_FONT_SIZE = 100;

console.log(`\n${"=".repeat(80)}`);
console.log(`  "fast jira" rendered at ${SCALED_FONT_SIZE}pt in ${FONT_FAMILY} (Blex Mono) - HIGH RES`);
console.log(`${"=".repeat(80)}\n`);

// High resolution rendering - large font with fine sampling
console.log("High Resolution (100pt, 1x2 cell sampling):\n");
const asciiHighRes = renderTextToAscii(TEXT, SCALED_FONT_SIZE, FONT_FAMILY, {
  cellWidth: 1,
  cellHeight: 2,
  charset: ASCII_CHARS_DETAILED,
  contrast: 1.2,
});
console.log(asciiHighRes);

// Save high-res to file
const outputPath = path.resolve(__dirname, "fast-jira-ascii.txt");
fs.writeFileSync(outputPath, asciiHighRes);
console.log(`Saved to: ${outputPath}\n`);

// Block characters version at high res
console.log("\nHigh Resolution Block Characters (100pt):\n");
const asciiBlocks = renderTextToAscii(TEXT, SCALED_FONT_SIZE, FONT_FAMILY, {
  cellWidth: 1,
  cellHeight: 2,
  charset: ASCII_CHARS_BLOCKS,
});
console.log(asciiBlocks);
