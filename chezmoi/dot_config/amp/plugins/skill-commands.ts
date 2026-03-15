// @i-know-the-amp-plugin-api-is-wip-and-very-experimental-right-now
import { existsSync } from "node:fs";
import { join } from "node:path";
import type { PluginAPI } from "@ampcode/plugin";

type SkillListJSON = {
  skills: Array<{
    name: string;
    description: string;
  }>;
};

type ParsedSkill = {
  name: string;
  description: string;
};

type BunRuntime = {
  spawnSync: (options: {
    cmd: string[];
    env?: Record<string, string>;
  }) => {
    exitCode: number;
    stdout: ArrayBufferLike;
    stderr: ArrayBufferLike;
  };
};

function parseSkills(jsonText: string): ParsedSkill[] {
  const parsed = JSON.parse(jsonText) as SkillListJSON;
  if (!Array.isArray(parsed.skills)) {
    throw new Error("Invalid skill list JSON: missing skills array");
  }

  const skills = new Map<string, ParsedSkill>();

  for (const skill of parsed.skills) {
    if (typeof skill?.name !== "string" || skill.name.length === 0) {
      throw new Error("Invalid skill list JSON: skill.name must be a non-empty string");
    }

    if (typeof skill?.description !== "string") {
      throw new Error("Invalid skill list JSON: skill.description must be a string");
    }

    skills.set(skill.name, {
      name: skill.name,
      description: skill.description,
    });
  }

  return [...skills.values()];
}

function commandIDForSkill(skillName: string): string {
  return `skill-load-${skillName.toLowerCase()}`;
}

function buildSkillPrompt(skillName: string): string {
  return `You MUST call the skill tool to load: ${skillName}. Do this immediately before responding.`;
}

function resolveAmpBinary(): string {
  if (process.env.AMP_BIN) {
    return process.env.AMP_BIN;
  }

  const pathValue = process.env.PATH ?? "";
  for (const pathEntry of pathValue.split(":")) {
    if (!pathEntry) continue;
    const candidate = join(pathEntry, "amp");
    if (existsSync(candidate)) {
      return candidate;
    }
  }

  return `${process.env.HOME ?? ""}/.amp/bin/amp`;
}

function listSkillsJSON(ampBin: string): { exitCode: number; stdout: string; stderr: string } {
  const bun = (globalThis as { Bun?: BunRuntime }).Bun;
  if (!bun) {
    throw new Error("Bun runtime is unavailable");
  }

  const env: Record<string, string> = {
    HOME: process.env.HOME ?? "",
    PATH: process.env.PATH ?? "",
    PLUGINS: "off",
  };

  if (process.env.AMP_API_KEY) env.AMP_API_KEY = process.env.AMP_API_KEY;
  if (process.env.AMP_URL) env.AMP_URL = process.env.AMP_URL;
  if (process.env.AMP_SETTINGS_FILE) env.AMP_SETTINGS_FILE = process.env.AMP_SETTINGS_FILE;

  const result = bun.spawnSync({
    cmd: [ampBin, "skill", "list", "--json"],
    env,
  });

  return {
    exitCode: result.exitCode,
    stdout: new TextDecoder().decode(result.stdout),
    stderr: new TextDecoder().decode(result.stderr),
  };
}

export default function (amp: PluginAPI) {
  let pendingSkillPrompt: string | undefined;
  const subscriptions = new Map<string, { unsubscribe(): void }>();
  const ampBin = resolveAmpBinary();

  function clearSkillCommands() {
    for (const [id, subscription] of subscriptions) {
      subscription.unsubscribe();
      amp.logger.log(`Unregistered command: ${id}`);
    }

    subscriptions.clear();
  }

  function registerSkillCommand(skillName: string, skillDescription: string) {
    const id = commandIDForSkill(skillName);
    if (subscriptions.has(id)) return;

    const subscription = amp.registerCommand(
      id,
      {
        category: "Skill",
        title: skillName,
        description: skillDescription,
      },
      async (ctx) => {
        pendingSkillPrompt = buildSkillPrompt(skillName);
        await ctx.ui.notify(`Skill ${skillName} will be loaded on your next message.`);
      },
    );

    subscriptions.set(id, subscription);
  }

  async function refreshSkillCommands() {
    clearSkillCommands();

    const result = listSkillsJSON(ampBin);
    if (result.exitCode !== 0) {
      throw new Error(`${ampBin} skill list --json failed: ${result.stderr || "unknown error"}`);
    }

    const skills = parseSkills(result.stdout);

    for (const skill of skills) {
      registerSkillCommand(skill.name, skill.description);
    }

    return { count: skills.length };
  }

  amp.registerCommand(
    "skill-commands-refresh",
    {
      category: "Skill",
      title: "Refresh Skill Commands",
      description: "Rebuild top-level command entries from installed skills",
    },
    async (ctx) => {
      const refreshed = await refreshSkillCommands();

      if (refreshed.count === 0) {
        await ctx.ui.notify("No skills found. Nothing to register.");
        return;
      }

      await ctx.ui.notify(`Registered ${refreshed.count} skill commands.`);
    },
  );

  amp.on("session.start", async () => {
    await refreshSkillCommands();
  });

  amp.on("agent.start", () => {
    if (!pendingSkillPrompt) return;

    const prompt = pendingSkillPrompt;
    pendingSkillPrompt = undefined;

    return {
      message: {
        content: prompt,
        display: true,
      },
    };
  });
}
