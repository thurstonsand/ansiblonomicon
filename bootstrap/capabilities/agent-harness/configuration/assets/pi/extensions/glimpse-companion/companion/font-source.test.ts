import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";

test("companion renders the font configured in the runtime HOME", () => {
  const fixture = mkdtempSync(join(tmpdir(), "companion-font-"));
  const home = join(fixture, "home");
  const glimpse = join(fixture, "glimpse");
  const output = join(fixture, "rendered.html");
  const fontFile = join(home, ".pi/agent/extensions/glimpse-companion/companion/font-family.txt");
  mkdirSync(join(glimpse, "src"), { recursive: true });
  mkdirSync(dirname(fontFile), { recursive: true });
  writeFileSync(fontFile, "Fixture Custom Mono\n");
  writeFileSync(
    join(glimpse, "src/glimpse.mjs"),
    `import { writeFileSync } from "node:fs";
export function open(html) { writeFileSync(process.env.COMPANION_TEST_OUTPUT, html); process.exit(0); }\n`,
  );

  const result = spawnSync(
    process.execPath,
    ["--import", "jiti/register", join(import.meta.dirname, "..", "companion.ts")],
    { env: { ...process.env, HOME: home, GLIMPSE_DIR: glimpse, COMPANION_TEST_OUTPUT: output } },
  );

  assert.equal(result.status, 0, result.stderr.toString());
  assert.match(readFileSync(output, "utf-8"), /Fixture Custom Mono/);
});
