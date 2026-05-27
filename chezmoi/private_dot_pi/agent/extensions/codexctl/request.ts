import type { Api, Model } from "@earendil-works/pi-ai";
import type { CodexSettings } from "./settings.js";
import { isObject } from "./settings.js";

type ResponsesPayload = Record<string, unknown> & {
  reasoning?: unknown;
  service_tier?: unknown;
  text?: unknown;
};

export function shouldApplyCodexSettings(model: Model<Api> | undefined): boolean {
  return model?.provider === "openai-codex";
}

export function applyCodexRequestSettings(payload: unknown, settings: CodexSettings): unknown {
  if (!isObject(payload)) return payload;

  const text = isObject(payload.text) ? payload.text : {};
  const next: ResponsesPayload = {
    ...payload,
    ...(settings.fast ? { service_tier: "priority" } : {}),
    text: { ...text, verbosity: settings.verbosity },
  };

  if (isObject(payload.reasoning)) {
    next.reasoning = { ...payload.reasoning, summary: settings.reasoningSummary };
  }

  return next;
}
