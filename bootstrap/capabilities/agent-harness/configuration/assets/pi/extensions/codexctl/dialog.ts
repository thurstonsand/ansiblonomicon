import type { ExtensionCommandContext } from "@earendil-works/pi-coding-agent";
import { applyCodexCommand, CODEX_USAGE, parseCodexCommand, saveAndAnnounce } from "./command.js";
import { shouldApplyCodexSettings } from "./request.js";
import {
  type CodexSettings,
  loadCodexSettingsState,
  REASONING_SUMMARY_VALUES,
  VERBOSITY_VALUES,
} from "./settings.js";

const KEEP_SETTINGS = "Keep current settings";

/**
 * The `/codex` panel for hosts that render only Pi's built-in dialogs, such as
 * RPC clients. One `select` picks the setting and a second picks its value.
 */
export async function promptCodexSettings(ctx: ExtensionCommandContext): Promise<void> {
  const settings = loadCodexSettingsState().settings;
  const fast = `Turn fast priority ${settings.fast ? "off" : "on"}`;
  const verbosity = `Change verbosity (now ${settings.verbosity})`;
  const summary = `Change reasoning summary (now ${settings.reasoningSummary})`;

  const answer = await ctx.ui.select(codexTitle(ctx), [fast, verbosity, summary, KEEP_SETTINGS]);
  if (answer === undefined || answer === KEEP_SETTINGS) return;

  let next: CodexSettings | undefined;
  if (answer === fast) {
    next = { ...settings, fast: !settings.fast };
  } else if (answer === verbosity) {
    const value = await pickValue(ctx, "Codex verbosity", VERBOSITY_VALUES, settings.verbosity);
    next = value && { ...settings, verbosity: value };
  } else if (answer === summary) {
    const value = await pickValue(
      ctx,
      "Codex reasoning summary",
      REASONING_SUMMARY_VALUES,
      settings.reasoningSummary,
    );
    next = value && { ...settings, reasoningSummary: value };
  } else {
    const parsed = parseCodexCommand(answer, false);
    if (parsed.kind === "error" || parsed.kind === "open-panel") {
      ctx.ui.notify(CODEX_USAGE, "error");
      return;
    }
    next = applyCodexCommand(settings, parsed);
  }

  if (next) saveAndAnnounce(ctx, next);
}

function codexTitle(ctx: ExtensionCommandContext): string {
  const model = ctx.model;
  const target = model
    ? `${shouldApplyCodexSettings(model) ? "Applies to" : "Not used by"} \`${model.provider}/${model.id}\`.`
    : "No model selected.";
  // T3 Code repeats the first line as plain text in its timeline, so it carries no Markdown.
  return `Codex settings\n\n${target}`;
}

async function pickValue<T extends string>(
  ctx: ExtensionCommandContext,
  title: string,
  values: readonly T[],
  current: T,
): Promise<T | undefined> {
  const labels = values.map((value) => (value === current ? `${value} (current)` : value));
  const answer = await ctx.ui.select(title, labels);
  if (answer === undefined) return undefined;
  const typed = answer.trim().toLowerCase();
  const value = values.find((value, index) => labels[index] === answer || value === typed);
  if (!value) ctx.ui.notify(`${title} must be one of ${values.join(", ")}`, "error");
  return value;
}
