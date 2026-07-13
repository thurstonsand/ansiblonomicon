import { deepStrictEqual, equal } from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import type { Api, Model } from "@earendil-works/pi-ai";
import {
  findExactModelReferenceMatch,
  restorePinnedDefaults,
  writePinnedDefaults,
} from "./index.js";

function withSettings(
  settings: string | Record<string, unknown>,
  run: (settingsPath: string) => void,
): void {
  const directory = mkdtempSync(join(tmpdir(), "pin-model-"));
  const settingsPath = join(directory, "settings.json");
  writeFileSync(
    settingsPath,
    typeof settings === "string" ? settings : JSON.stringify(settings),
    "utf8",
  );
  try {
    run(settingsPath);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

function readSettings(settingsPath: string): Record<string, unknown> {
  return JSON.parse(readFileSync(settingsPath, "utf8")) as Record<string, unknown>;
}

function model(provider: string, id: string): Model<Api> {
  return { provider, id } as Model<Api>;
}

test("restore initializes a missing pin without changing other settings", () => {
  withSettings(
    {
      defaultProvider: "anthropic",
      defaultModel: "claude-opus",
      defaultThinkingLevel: "high",
      nested: { preserved: true },
    },
    (settingsPath) => {
      equal(restorePinnedDefaults(settingsPath), "changed");
      deepStrictEqual(readSettings(settingsPath), {
        defaultProvider: "anthropic",
        defaultModel: "claude-opus",
        defaultThinkingLevel: "high",
        nested: { preserved: true },
        pinnedModel: {
          provider: "anthropic",
          modelId: "claude-opus",
          thinkingLevel: "high",
        },
      });
    },
  );
});

test("restore heals all defaults from the file-resident pin", () => {
  withSettings(
    {
      defaultProvider: "openai-codex",
      defaultModel: "temporary",
      defaultThinkingLevel: "low",
      pinnedModel: {
        provider: "anthropic",
        modelId: "claude-opus",
        thinkingLevel: "high",
      },
      preserved: "yes",
    },
    (settingsPath) => {
      equal(restorePinnedDefaults(settingsPath), "changed");
      deepStrictEqual(readSettings(settingsPath), {
        defaultProvider: "anthropic",
        defaultModel: "claude-opus",
        defaultThinkingLevel: "high",
        pinnedModel: {
          provider: "anthropic",
          modelId: "claude-opus",
          thinkingLevel: "high",
        },
        preserved: "yes",
      });
      equal(restorePinnedDefaults(settingsPath), "unchanged");
    },
  );
});

test("pin writes the pin and protected defaults together", () => {
  withSettings({ preserved: true }, (settingsPath) => {
    equal(
      writePinnedDefaults(settingsPath, {
        provider: "openai-codex",
        modelId: "gpt-5",
        thinkingLevel: "medium",
      }),
      "changed",
    );
    deepStrictEqual(readSettings(settingsPath), {
      preserved: true,
      pinnedModel: {
        provider: "openai-codex",
        modelId: "gpt-5",
        thinkingLevel: "medium",
      },
      defaultProvider: "openai-codex",
      defaultModel: "gpt-5",
      defaultThinkingLevel: "medium",
    });
  });
});

test("an unparseable settings file is never rewritten", () => {
  withSettings("{invalid", (settingsPath) => {
    equal(restorePinnedDefaults(settingsPath), "failed");
    equal(readFileSync(settingsPath, "utf8"), "{invalid");
  });
});

test("exact matching accepts canonical references and unique bare ids", () => {
  const models = [
    model("anthropic", "shared"),
    model("openai", "shared"),
    model("openai", "unique"),
  ];
  equal(findExactModelReferenceMatch(" OPENAI/shared ", models), models[1]);
  equal(findExactModelReferenceMatch("unique", models), models[2]);
  equal(findExactModelReferenceMatch("shared", models), undefined);
  equal(findExactModelReferenceMatch("openai/missing", models), undefined);
});
