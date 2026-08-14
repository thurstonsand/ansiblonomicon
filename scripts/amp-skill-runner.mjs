#!/usr/bin/env node

import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { dirname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const skillDir = dirname(fileURLToPath(import.meta.url));
const bundleData = readFileSync(join(skillDir, "bundle.json"), "utf8");
const bundleHash = createHash("sha256").update(bundleData).digest("hex");
const cacheRoot = join(
  process.env.XDG_CACHE_HOME || join(homedir(), ".cache"),
  "impeccable",
  bundleHash,
);

if (!existsSync(join(cacheRoot, ".ready"))) {
  const temporaryRoot = `${cacheRoot}.${process.pid}`;
  rmSync(temporaryRoot, { recursive: true, force: true });

  for (const [relativePath, file] of Object.entries(JSON.parse(bundleData))) {
    if (normalize(relativePath) !== relativePath || relativePath.startsWith("..")) {
      throw new Error(`Unsafe bundled path: ${relativePath}`);
    }

    const destination = join(temporaryRoot, relativePath);
    mkdirSync(dirname(destination), { recursive: true });
    writeFileSync(destination, Buffer.from(file.content, file.encoding));
  }

  writeFileSync(join(temporaryRoot, ".ready"), "");
  mkdirSync(dirname(cacheRoot), { recursive: true });
  try {
    renameSync(temporaryRoot, cacheRoot);
  } catch (error) {
    rmSync(temporaryRoot, { recursive: true, force: true });
    if (!existsSync(join(cacheRoot, ".ready"))) {
      throw error;
    }
  }
}

const [script, ...args] = process.argv.slice(2);
if (!script || normalize(script) !== script || script.startsWith("..")) {
  throw new Error("Usage: run.mjs <script> [arguments...]");
}

const scriptsRoot = resolve(cacheRoot, "scripts");
const target = resolve(scriptsRoot, script);
if (!target.startsWith(`${scriptsRoot}/`) || !existsSync(target)) {
  throw new Error(`Unknown bundled script: ${script}`);
}

const result = spawnSync(process.execPath, [target, ...args], {
  cwd: process.cwd(),
  env: process.env,
  stdio: "inherit",
});

if (result.error) {
  throw result.error;
}
if (result.signal) {
  process.kill(process.pid, result.signal);
}
process.exit(result.status ?? 1);
