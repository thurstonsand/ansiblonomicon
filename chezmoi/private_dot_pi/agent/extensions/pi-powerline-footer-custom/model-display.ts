import type { ThinkingLevel } from "@earendil-works/pi-agent-core";
import type { Api, Model } from "@earendil-works/pi-ai";
import type { ExtensionContext, ThemeColor } from "@earendil-works/pi-coding-agent";

import type { CodexStatus } from "./codexctl-config.js";

const STATUS_KEY = "model_display";
const FAST_ICON = "⚡︎";
const FALLBACK_ICON = "◈";
const ICON_PROVIDERS = ["anthropic", "google", "openai"] as const;
const VERBOSITY_ICONS: Record<NonNullable<CodexStatus["verbosity"]>, string> = {
  high: "●",
  medium: "◐",
  low: "◔",
};
const SUMMARY_ICONS: Record<NonNullable<CodexStatus["reasoningSummary"]>, string> = {
  auto: "Σ",
  concise: "Σ-",
  detailed: "Σ+",
  off: "Σ×",
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
  max: "⁴",
};

export function updateModelDisplayStatus(
  ctx: ExtensionContext,
  thinkingLevel: ThinkingLevel,
  codexStatus: CodexStatus | undefined,
): void {
  const model = ctx.model;
  const provider = getModelProvider(model);
  const name = formatModelName(model);
  const icon = provider ? PROVIDER_ICONS[provider] : FALLBACK_ICON;
  const status = model ? formatModelStatus(codexStatus) : "";
  const label = `${icon} ${applyThinkingExponent(name, thinkingLevel)}${status}`;

  ctx.ui.setStatus(STATUS_KEY, ctx.ui.theme.fg(providerColor(provider), label));
}

function formatModelName(model: Model<Api> | undefined): string {
  const rawName = model?.name || model?.id || "no model";
  return rawName.replace(/^(anthropic|openai|google)\//i, "").replace(/-/g, " ");
}

function formatModelStatus(codexStatus: CodexStatus | undefined): string {
  const parts = [
    codexStatus?.verbosity ? VERBOSITY_ICONS[codexStatus.verbosity] : undefined,
    codexStatus?.reasoningSummary ? SUMMARY_ICONS[codexStatus.reasoningSummary] : undefined,
    codexStatus?.fast ? FAST_ICON : undefined,
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
