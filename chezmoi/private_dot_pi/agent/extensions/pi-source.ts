import { spawn } from "node:child_process";
import { existsSync, mkdirSync, renameSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { type ExtensionAPI, VERSION } from "@earendil-works/pi-coding-agent";

const REPO_URL = "https://github.com/earendil-works/pi-mono.git";
const CACHE_ROOT = path.join(os.homedir(), ".cache", "pi-source");

// VERSION resolves to the running pi instance via the loader's module alias,
// not the local node_modules copy — the same constant pi uses to build its
// own doc paths, so the cloned source always matches the running binary.
const CHECKOUT_DIR = path.join(CACHE_ROOT, `v${VERSION}`);

let cloning = false;

function ensureClone(): void {
  if (VERSION === "0.0.0") return;
  if (existsSync(path.join(CHECKOUT_DIR, ".git"))) return;
  if (cloning) return;
  cloning = true;

  mkdirSync(CACHE_ROOT, { recursive: true });
  const tmpDir = `${CHECKOUT_DIR}.tmp-${process.pid}`;
  rmSync(tmpDir, { recursive: true, force: true });

  const child = spawn(
    "git",
    ["clone", "--depth", "1", "--branch", `v${VERSION}`, REPO_URL, tmpDir],
    { stdio: "ignore" },
  );

  child.on("error", () => {
    cloning = false;
    rmSync(tmpDir, { recursive: true, force: true });
  });

  child.on("exit", (code) => {
    cloning = false;
    if (code === 0 && !existsSync(path.join(CHECKOUT_DIR, ".git"))) {
      try {
        renameSync(tmpDir, CHECKOUT_DIR);
      } catch {
        rmSync(tmpDir, { recursive: true, force: true });
      }
    } else {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });
}

// Pi assembles the prompt in a fixed order and only lets extensions hand back a finished
// string, so both sections are spliced onto markers instead of appended at the end.
const FIRST_PARAGRAPH_END = "\n\n";
const DOCS_BLOCK_END =
  "- Always read pi .md files completely and follow links to related docs (e.g., tui.md for TUI API details)";

function insertBefore(prompt: string, marker: string, section: string): string {
  const at = prompt.indexOf(marker);
  if (at < 0) return prompt + section;
  return prompt.slice(0, at) + section + prompt.slice(at);
}

function insertAfter(prompt: string, marker: string, section: string): string {
  const at = prompt.indexOf(marker);
  if (at < 0) return prompt + section;
  const end = at + marker.length;
  return prompt.slice(0, end) + section + prompt.slice(end);
}

function sourceSection(): string {
  const packages = path.join(CHECKOUT_DIR, "packages");
  return `

Pi v${VERSION} source — read when the docs do not cover pi's internals (tools, agent loop, AI providers, TUI): ${packages}/{coding-agent,agent,ai,tui}/src
- The exact TypeScript source of the running binary. Read it and follow imports before implementing rather than guessing.`;
}

export default function (pi: ExtensionAPI): void {
  if (VERSION === "0.0.0") return;
  ensureClone();

  pi.on("before_agent_start", async (event, ctx) => {
    ensureClone();
    const model = ctx.model;
    const withSource = insertAfter(event.systemPrompt, DOCS_BLOCK_END, sourceSection());
    if (!model) return { systemPrompt: withSource };

    return {
      systemPrompt: insertBefore(
        withSource,
        FIRST_PARAGRAPH_END,
        `\n\nYou are the model ${model.provider}/${model.id}.`,
      ),
    };
  });
}
