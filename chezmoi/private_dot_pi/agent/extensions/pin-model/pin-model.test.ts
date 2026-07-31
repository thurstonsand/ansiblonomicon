import { deepStrictEqual, equal } from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import type { ThinkingLevel } from "@earendil-works/pi-agent-core";
import type { Api, Model } from "@earendil-works/pi-ai";
import type { ScopedModel } from "@earendil-works/pi-coding-agent";
import type { AutocompleteItem } from "@earendil-works/pi-tui";
import pinModelExtension, {
  findExactModelReferenceMatch,
  parseModelArgument,
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

async function withSettingsAsync(
  settings: Record<string, unknown>,
  run: (settingsPath: string, directory: string) => Promise<void>,
): Promise<void> {
  const directory = mkdtempSync(join(tmpdir(), "pin-model-"));
  const settingsPath = join(directory, "settings.json");
  writeFileSync(settingsPath, JSON.stringify(settings), "utf8");
  try {
    await run(settingsPath, directory);
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

/** A model whose catalogue entry advertises extended thinking. */
function thinkingModel(provider: string, id: string): Model<Api> {
  return { provider, id, reasoning: true } as Model<Api>;
}

function scoped(model: Model<Api>, thinkingLevel?: ThinkingLevel): ScopedModel {
  return { model, thinkingLevel };
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
    scoped(model("anthropic", "shared")),
    scoped(model("openai", "shared")),
    scoped(model("openai", "unique")),
  ];
  equal(findExactModelReferenceMatch(" OPENAI/shared ", models), models[1]);
  equal(findExactModelReferenceMatch("unique", models), models[2]);
  equal(findExactModelReferenceMatch("shared", models), undefined);
  equal(findExactModelReferenceMatch("openai/missing", models), undefined);
});

test("a trailing colon is a thinking level only when it names one", () => {
  deepStrictEqual(parseModelArgument("sonnet:high"), {
    reference: "sonnet",
    thinkingLevel: "high",
  });
  deepStrictEqual(parseModelArgument(" sonnet "), { reference: "sonnet" });
  deepStrictEqual(parseModelArgument(""), { reference: "" });
  // Bedrock ids carry their own colon; `0` is not a thinking level.
  deepStrictEqual(parseModelArgument("amazon-bedrock/anthropic.claude-opus-4-5-v1:0"), {
    reference: "amazon-bedrock/anthropic.claude-opus-4-5-v1:0",
  });
  // A colon suffix that names nothing stays part of the reference, so the
  // caller reports "no models match" rather than silently dropping it.
  deepStrictEqual(parseModelArgument("sonnet:bogus"), { reference: "sonnet:bogus" });
});

interface PinModelCommand {
  getArgumentCompletions(prefix: string): AutocompleteItem[] | null;
  handler(args: string, ctx: unknown): Promise<void>;
}

interface ExtensionHarness {
  command: PinModelCommand;
  ctx: unknown;
  /** Fires session_start, the point at which pin-model captures ctx. */
  startSession(): void;
  refreshCalls(): number;
  thinkingLevel(): ThinkingLevel;
  notices: string[];
}

async function withExtension(
  options: {
    available: Model<Api>[];
    scopedModels?: ScopedModel[];
    settings?: Record<string, unknown>;
    thinkingLevel?: ThinkingLevel;
  },
  run: (harness: ExtensionHarness, settingsPath: string) => Promise<void>,
): Promise<void> {
  const settings = options.settings ?? {
    defaultProvider: "openai",
    defaultModel: "test-model",
    defaultThinkingLevel: "off",
  };

  await withSettingsAsync(settings, async (settingsPath, agentDir) => {
    const previousAgentDir = process.env.PI_CODING_AGENT_DIR;
    process.env.PI_CODING_AGENT_DIR = agentDir;
    try {
      const handlers = new Map<string, (...args: never[]) => unknown>();
      let command: PinModelCommand | undefined;
      let refreshCalls = 0;
      let thinkingLevel = options.thinkingLevel ?? "off";
      const notices: string[] = [];
      const pi = {
        getThinkingLevel: () => thinkingLevel,
        setThinkingLevel: (level: ThinkingLevel) => {
          thinkingLevel = level;
        },
        on: (event: string, handler: (...args: never[]) => unknown) => {
          handlers.set(event, handler);
        },
        registerCommand: (_name: string, definition: PinModelCommand) => {
          command = definition;
        },
        setModel: async () => true,
      };

      pinModelExtension(pi as never);
      if (!command) throw new Error("pin-model command was not registered");

      const ctx = {
        model: options.available[0],
        modelRegistry: {
          refresh: async () => {
            refreshCalls += 1;
          },
          getAvailable: () => options.available,
        },
        scopedModels: options.scopedModels ?? [],
        ui: {
          notify: (message: string) => notices.push(message),
          select: async () => undefined,
        },
      };

      await run(
        {
          command,
          ctx,
          startSession: () => {
            const sessionStart = handlers.get("session_start");
            if (!sessionStart) throw new Error("session_start handler was not registered");
            sessionStart({} as never, ctx as never);
          },
          refreshCalls: () => refreshCalls,
          thinkingLevel: () => thinkingLevel,
          notices,
        },
        settingsPath,
      );
    } finally {
      if (previousAgentDir === undefined) {
        delete process.env.PI_CODING_AGENT_DIR;
      } else {
        process.env.PI_CODING_AGENT_DIR = previousAgentDir;
      }
    }
  });
}

test("reads the model registry without ever refreshing it", async () => {
  const availableModel = model("openai", "test-model");
  const otherModel = model("openai", "other-model");

  await withExtension(
    { available: [availableModel, otherModel] },
    async (harness, settingsPath) => {
      // session_start exists only to capture ctx: completions are unavailable before it
      // and available the instant it returns, without waiting on anything.
      deepStrictEqual(harness.command.getArgumentCompletions("test"), null);
      harness.startSession();
      equal(harness.command.getArgumentCompletions("test")?.[0]?.value, "openai/test-model");

      await harness.command.handler("openai/other-model", harness.ctx);
      equal(readSettings(settingsPath).defaultModel, "other-model");
      equal(harness.refreshCalls(), 0);
    },
  );
});

test("a scoped session offers and pins only its scoped models", async () => {
  const scopedModel = model("openai", "scoped-model");
  const unscopedModel = model("anthropic", "unscoped-model");

  await withExtension(
    { available: [scopedModel, unscopedModel], scopedModels: [{ model: scopedModel }] },
    async (harness, settingsPath) => {
      harness.startSession();

      deepStrictEqual(
        harness.command.getArgumentCompletions("model")?.map((item) => item.value),
        ["openai/scoped-model"],
      );

      await harness.command.handler("anthropic/unscoped-model", harness.ctx);
      equal(readSettings(settingsPath).defaultModel, "test-model");
      equal(harness.notices.at(-1), 'No models match "anthropic/unscoped-model"');

      await harness.command.handler("openai/scoped-model", harness.ctx);
      equal(readSettings(settingsPath).defaultModel, "scoped-model");
    },
  );
});

test("switching to a scoped model adopts its configured thinking level", async () => {
  const current = thinkingModel("anthropic", "opus");
  const target = thinkingModel("anthropic", "sonnet");

  await withExtension(
    {
      available: [current, target],
      scopedModels: [scoped(current, "medium"), scoped(target, "high")],
      thinkingLevel: "medium",
    },
    async (harness, settingsPath) => {
      harness.startSession();

      // Without the configured level this would inherit "medium" from the
      // outgoing model, disagreeing with what pi's own cycler produces.
      await harness.command.handler("anthropic/sonnet", harness.ctx);
      equal(harness.thinkingLevel(), "high");
      equal(readSettings(settingsPath).defaultThinkingLevel, "high");
    },
  );
});

test("an explicit level overrides the configured one", async () => {
  const target = thinkingModel("anthropic", "sonnet");

  await withExtension(
    { available: [target], scopedModels: [scoped(target, "high")], thinkingLevel: "medium" },
    async (harness, settingsPath) => {
      harness.startSession();

      await harness.command.handler("anthropic/sonnet:low", harness.ctx);
      equal(harness.thinkingLevel(), "low");
      equal(readSettings(settingsPath).defaultThinkingLevel, "low");
    },
  );
});

test("a model with no configured level inherits the current one", async () => {
  const target = thinkingModel("anthropic", "sonnet");

  await withExtension(
    { available: [target], scopedModels: [scoped(target)], thinkingLevel: "medium" },
    async (harness, settingsPath) => {
      harness.startSession();

      await harness.command.handler("anthropic/sonnet", harness.ctx);
      equal(harness.thinkingLevel(), "medium");
      equal(readSettings(settingsPath).defaultThinkingLevel, "medium");
    },
  );
});

test("a level the model cannot support is refused rather than clamped", async () => {
  const target = model("anthropic", "haiku");

  await withExtension(
    { available: [target], scopedModels: [scoped(target)], thinkingLevel: "off" },
    async (harness, settingsPath) => {
      harness.startSession();

      await harness.command.handler("anthropic/haiku:high", harness.ctx);
      equal(harness.notices.at(-1), "haiku supports only: off");
      equal(readSettings(settingsPath).defaultModel, "test-model");
    },
  );
});

test("completions surface configured levels and a model's own supported levels", async () => {
  const sonnet = thinkingModel("anthropic", "sonnet");
  const haiku = model("anthropic", "haiku");

  await withExtension(
    { available: [sonnet, haiku], scopedModels: [scoped(sonnet, "high"), scoped(haiku)] },
    async (harness) => {
      harness.startSession();

      // A configured level rides along on the model completion, so accepting it
      // shows exactly what will be pinned.
      deepStrictEqual(
        harness.command.getArgumentCompletions("sonnet")?.map((item) => item.value),
        ["anthropic/sonnet:high"],
      );
      deepStrictEqual(
        harness.command.getArgumentCompletions("haiku")?.map((item) => item.value),
        ["anthropic/haiku"],
      );

      // An exact model before the colon switches completion over to its levels.
      deepStrictEqual(
        harness.command.getArgumentCompletions("anthropic/sonnet:")?.map((item) => item.label),
        ["off", "minimal", "low", "medium", "high"],
      );
      deepStrictEqual(
        harness.command.getArgumentCompletions("anthropic/sonnet:h")?.map((item) => item.value),
        ["anthropic/sonnet:high"],
      );
      // A model that cannot think offers nothing to choose from but "off".
      deepStrictEqual(
        harness.command.getArgumentCompletions("anthropic/haiku:")?.map((item) => item.label),
        ["off"],
      );
    },
  );
});

test("an unscoped session falls back to the whole catalogue", async () => {
  const first = model("openai", "test-model");
  const second = model("anthropic", "catalogue-only");

  await withExtension({ available: [first, second] }, async (harness, settingsPath) => {
    harness.startSession();

    await harness.command.handler("anthropic/catalogue-only", harness.ctx);
    equal(readSettings(settingsPath).defaultModel, "catalogue-only");
  });
});
