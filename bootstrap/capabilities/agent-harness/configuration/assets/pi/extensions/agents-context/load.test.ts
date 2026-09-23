import { deepStrictEqual, equal } from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { collectContextFiles, type ReferenceNotifier } from "./load.js";
import { renderBlocks } from "./render.js";

function withDirectory(run: (directory: string) => void): void {
  const directory = mkdtempSync(join(tmpdir(), "agents-context-"));
  try {
    run(directory);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

function notifier(messages: string[]): ReferenceNotifier {
  return {
    notify(message) {
      messages.push(message);
    },
  };
}

test("loads a case-insensitive AGENTS.local.md companion and follows its references", () => {
  withDirectory((directory) => {
    const agentsPath = join(directory, "AGENTS.md");
    const localPath = join(directory, "AgEnTs.LoCaL.mD");
    const detailPath = join(directory, "local-detail.md");
    writeFileSync(agentsPath, "Shared instructions", "utf8");
    writeFileSync(localPath, "Local instructions\n@local-detail.md", "utf8");
    writeFileSync(detailPath, "Local detail", "utf8");

    const messages: string[] = [];
    const loaded = collectContextFiles(
      [{ path: agentsPath, content: "Shared instructions" }],
      [{ path: agentsPath }],
      5,
      notifier(messages),
    );

    deepStrictEqual(
      loaded.map(({ resolvedPath, source }) => ({ resolvedPath, source })),
      [
        { resolvedPath: localPath, source: { type: "local", from: agentsPath } },
        {
          resolvedPath: detailPath,
          source: { type: "reference", ref: "local-detail.md", from: localPath },
        },
      ],
    );
    deepStrictEqual(messages, []);
  });
});

test("does not load an automatically discovered local companion twice", () => {
  withDirectory((directory) => {
    const agentsPath = join(directory, "AGENTS.md");
    const localPath = join(directory, "AGENTS.local.md");
    writeFileSync(localPath, "Local instructions", "utf8");

    const loaded = collectContextFiles(
      [{ path: agentsPath, content: "@AGENTS.local.md" }],
      [{ path: agentsPath }],
      5,
      notifier([]),
    );

    equal(loaded.length, 1);
    deepStrictEqual(loaded[0], {
      resolvedPath: localPath,
      source: { type: "local", from: agentsPath },
      content: "Local instructions",
    });
  });
});

test("CLAUDE.md follows references and loads only CLAUDE.local.md", () => {
  withDirectory((directory) => {
    const claudePath = join(directory, "CLAUDE.md");
    const claudeLocalPath = join(directory, "CLAUDE.local.md");
    const agentsLocalPath = join(directory, "AGENTS.local.md");
    const detailPath = join(directory, "claude-detail.md");
    writeFileSync(claudeLocalPath, "Claude local instructions", "utf8");
    writeFileSync(agentsLocalPath, "Agents local instructions", "utf8");
    writeFileSync(detailPath, "Claude detail", "utf8");

    const loaded = collectContextFiles(
      [{ path: claudePath, content: "@claude-detail.md" }],
      [{ path: claudePath }],
      5,
      notifier([]),
    );

    deepStrictEqual(
      loaded.map(({ resolvedPath, source }) => ({ resolvedPath, source })),
      [
        { resolvedPath: claudeLocalPath, source: { type: "local", from: claudePath } },
        {
          resolvedPath: detailPath,
          source: { type: "reference", ref: "claude-detail.md", from: claudePath },
        },
      ],
    );
  });
});

test("loads AGENTS.local.md beside a referenced AGENTS.md", () => {
  withDirectory((directory) => {
    const rootPath = join(directory, "AGENTS.md");
    const nestedDirectory = join(directory, "nested");
    const nestedPath = join(nestedDirectory, "AGENTS.md");
    const nestedLocalPath = join(nestedDirectory, "AGENTS.local.md");
    mkdirSync(nestedDirectory);
    writeFileSync(nestedPath, "Nested instructions", "utf8");
    writeFileSync(nestedLocalPath, "Nested local instructions", "utf8");

    const loaded = collectContextFiles(
      [{ path: rootPath, content: "@nested/AGENTS.md" }],
      [{ path: rootPath }],
      5,
      notifier([]),
    );

    equal(loaded.length, 2);
    deepStrictEqual(loaded[1]?.source, { type: "local", from: nestedPath });
    equal(loaded[1]?.resolvedPath, nestedLocalPath);
  });
});

test("renders local files like native project context and references separately", () => {
  const rendered = renderBlocks([
    {
      resolvedPath: "/project/AGENTS.local.md",
      source: { type: "local", from: "/project/AGENTS.md" },
      content: "Local instructions",
    },
    {
      resolvedPath: "/project/details.md",
      source: { type: "reference", ref: "details.md", from: "/project/AGENTS.md" },
      content: "Referenced instructions",
    },
  ]);

  equal(
    rendered,
    '\n\n<project_context>\n\nProject-specific instructions and guidelines:\n\n<project_instructions path="/project/AGENTS.local.md">\nLocal instructions\n</project_instructions>\n\n</project_context>\n\n\n<referenced_context>\n\nFile pulled in via @-reference from /project/AGENTS.md:\n\n<project_instructions path="/project/details.md" referenced-as="@details.md" referenced-from="/project/AGENTS.md">\nReferenced instructions\n</project_instructions>\n\n</referenced_context>\n',
  );
});

test("ignores missing AGENTS.local.md without notifying", () => {
  withDirectory((directory) => {
    const agentsPath = join(directory, "AGENTS.md");
    const messages: string[] = [];

    const loaded = collectContextFiles(
      [{ path: agentsPath, content: "Shared instructions" }],
      [{ path: agentsPath }],
      5,
      notifier(messages),
    );

    deepStrictEqual(loaded, []);
    deepStrictEqual(messages, []);
  });
});
