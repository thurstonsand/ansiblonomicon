#!/usr/bin/env node
// Pi installs git packages with `npm install --omit=dev`, but npm still
// resolves dev dependencies. Packages pin @earendil-works/pi-* dev versions the
// work mirror may lack, and Pi supplies those modules at runtime anyway, so a
// git-package install drops them from package.json for the duration of the run.
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const args = process.argv.slice(2);
const manifest = "package.json";
let original;
if (args.length === 1 && args[0] === "install") {
  args.push("--omit=dev");
  original = readFileSync(manifest, "utf8");
}
if (original !== undefined) {
  const parsed = JSON.parse(original);
  const dev = parsed.devDependencies ?? {};
  const kept = Object.fromEntries(
    Object.entries(dev).filter(([name]) => !name.startsWith("@earendil-works/pi-")),
  );
  if (Object.keys(kept).length === Object.keys(dev).length) {
    original = undefined;
  } else {
    parsed.devDependencies = kept;
    writeFileSync(manifest, `${JSON.stringify(parsed, null, 2)}\n`);
  }
}
const result = spawnSync("npm", args, { stdio: "inherit" });
if (original !== undefined) {
  writeFileSync(manifest, original);
}
if (result.error) {
  throw result.error;
}
process.exit(result.status ?? 1);
