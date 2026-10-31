import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { HunkExtensionAPI } from "hunkdiff/extension";

// Omarchy renders hunk-theme.json for whichever theme is active.
export default function (hunk: HunkExtensionAPI) {
  hunk.registerTheme(
    JSON.parse(readFileSync(join(homedir(), ".local/state/omarchy/current/theme/hunk-theme.json"), "utf8")),
  );
}
