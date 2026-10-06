#!/usr/bin/env node
// Pi installs git packages with `npm install --omit=dev`, but npm still
// resolves dev dependencies, and any the work mirror lacks fail the install.
// None are installed anyway, so a git-package install drops them from
// package.json for the duration of the run.
// It also bypasses the lockfile: its pins may predate the mirror, and npm would
// otherwise prune the dropped entries from the clone's tracked lockfile.
// Pi's npmCommand names npm after `--`, which tells Pi to pass its npm-specific
// peer suppression through this wrapper.
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const [separator, npm, ...args] = process.argv.slice(2);
if (separator !== "--" || !npm) {
  throw new Error("usage: npm-mirror-shim.mjs -- npm [args...]");
}
const manifest = "package.json";
let original;
if (args[0] === "install" && args.slice(1).every((arg) => arg.startsWith("-"))) {
  args.push("--no-package-lock");
  original = readFileSync(manifest, "utf8");
  const parsed = JSON.parse(original);
  if (parsed.devDependencies === undefined) {
    original = undefined;
  } else {
    delete parsed.devDependencies;
    writeFileSync(manifest, `${JSON.stringify(parsed, null, 2)}\n`);
  }
}
const result = spawnSync(npm, args, { stdio: "inherit" });
if (original !== undefined) {
  writeFileSync(manifest, original);
}
if (result.error) {
  throw result.error;
}
process.exit(result.status ?? 1);
