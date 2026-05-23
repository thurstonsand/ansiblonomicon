import type { ThinkingLevel } from "@earendil-works/pi-agent-core";
import type { Api, Model } from "@earendil-works/pi-ai";
import type { ExtensionContext, ThemeColor } from "@earendil-works/pi-coding-agent";

import type { CodexConversionStatus } from "./codex-conversion-config.js";

const STATUS_KEY = "model_display";
const FAST_ICON = "⚡︎";
const FALLBACK_ICON = "◈";
const ICON_PROVIDERS = ["anthropic", "google", "openai"] as const;
const VERBOSITY_ICONS: Record<NonNullable<CodexConversionStatus["verbosity"]>, string> = {
  high: "●",
  medium: "◐",
  low: "◔",
};
const ICON_PROVIDER_SET: ReadonlySet<string> = new Set(ICON_PROVIDERS);

type IconProvider = (typeof ICON_PROVIDERS)[number];

const PROVIDER_ICONS: Record<IconProvider, string> = {
  anthropic: "✴",
  google: "✦",
  openai: "❁",
};

const PROVIDER_COLORS: Record<IconProvider, ThemeColor> = {
  anthropic: "syntaxNumber",
  google: "thinkingLow",
  openai: "text",
};

const PROVIDER_HINTS: ReadonlyArray<readonly [hint: string, provider: IconProvider]> = [
  ["anthropic", "anthropic"],
  ["claude", "anthropic"],
  ["openai", "openai"],
  ["gpt", "openai"],
  ["codex", "openai"],
  ["google", "google"],
  ["gemini", "google"],
];

const THINKING_EXPONENTS: Partial<Record<ThinkingLevel, string>> = {
  off: "⁻³",
  minimal: "⁻²",
  low: "⁻¹",
  high: "²",
  xhigh: "³",
};

export function updateModelDisplayStatus(
  ctx: ExtensionContext,
  thinkingLevel: ThinkingLevel,
  codexConversionStatus: CodexConversionStatus | undefined,
): void {
  const model = ctx.model;
  const provider = getModelProvider(model);
  const name = formatModelName(model);
  const icon = provider ? PROVIDER_ICONS[provider] : FALLBACK_ICON;
  const status = model ? formatModelStatus(codexConversionStatus) : "";
  const label = `${icon} ${applyThinkingExponent(name, thinkingLevel)}${status}`;

  ctx.ui.setStatus(STATUS_KEY, ctx.ui.theme.fg(providerColor(provider), label));
}

function formatModelName(model: Model<Api> | undefined): string {
  const rawName = model?.name || model?.id || "no model";
  return rawName.replace(/^(anthropic|openai|google)\//i, "").replace(/-/g, " ");
}

function formatModelStatus(codexConversionStatus: CodexConversionStatus | undefined): string {
  const parts = [
    codexConversionStatus?.verbosity ? VERBOSITY_ICONS[codexConversionStatus.verbosity] : undefined,
    codexConversionStatus?.fast ? FAST_ICON : undefined,
  ].filter(Boolean);
  return parts.length > 0 ? ` [${parts.join(" ")}]` : "";
}

function getModelProvider(model: Model<Api> | undefined): IconProvider | undefined {
  if (isIconProvider(model?.provider)) return model.provider;

  const candidate = `${model?.id ?? ""} ${model?.name ?? ""}`.toLowerCase();
  return PROVIDER_HINTS.find(([hint]) => candidate.includes(hint))?.[1];
}

function providerColor(provider: IconProvider | undefined): ThemeColor {
  return provider ? PROVIDER_COLORS[provider] : "accent";
}

function isIconProvider(value: unknown): value is IconProvider {
  return typeof value === "string" && ICON_PROVIDER_SET.has(value);
}

function applyThinkingExponent(label: string, thinkingLevel: ThinkingLevel): string {
  const exponent = THINKING_EXPONENTS[thinkingLevel];
  return exponent ? `${label}${exponent}` : label;
}
