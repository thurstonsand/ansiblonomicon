import type { SegmentContext, SegmentLoaderAPI, StatusLineSegment } from "pi-powerline-footer";
import { SEP_DOT, type ModelSegmentOptions } from "./constants.js";
import { isFastEnabled, getFastStyle, formatFast, colorForFast } from "./fast.js";
import { applyThinkingExponent } from "./label.js";
import { applyColor, getModelIcon, getThinkingText, withIcon } from "./theme.js";
import { colorForVerbosity, formatVerbosity, getVerbosityStyle, resolveVerbosity } from "./verbosity.js";

function getModelProvider(model: SegmentContext["model"] | undefined): string | undefined {
  const runtimeProvider = (model as (SegmentContext["model"] & { provider?: string }) | undefined)?.provider;
  if (runtimeProvider) {
    return runtimeProvider;
  }

  const candidate = `${model?.id ?? ""} ${model?.name ?? ""}`.toLowerCase();
  if (candidate.includes("anthropic") || candidate.includes("claude")) {
    return "anthropic";
  }
  if (candidate.includes("openai") || candidate.includes("gpt") || candidate.includes("codex")) {
    return "openai";
  }
  if (candidate.includes("google") || candidate.includes("gemini")) {
    return "google";
  }

  return undefined;
}

export default function ({ registerSegment }: SegmentLoaderAPI): void {
  const segment: StatusLineSegment<ModelSegmentOptions> = {
    id: "model",
    render(ctx: SegmentContext, options) {
      const opts = options ?? ctx.options.model ?? {};

      const rawDisplayName = ctx.model?.name || ctx.model?.id || "no-model";

      const displayName = applyThinkingExponent(rawDisplayName, ctx.thinkingLevel);

      let primary = withIcon(getModelIcon(getModelProvider(ctx.model)), displayName);

      if (opts.showThinkingLevel !== false && ctx.model?.reasoning) {
        const level = ctx.thinkingLevel || "off";
        if (level !== "off") {
          const thinkingText = getThinkingText(level);
          if (thinkingText) {
            primary += `${SEP_DOT}${thinkingText}`;
          }
        }
      }

      const modelColor = ctx.colors?.model ?? "accent";
      const parts = [applyColor(ctx.theme, modelColor, primary)];

      const verbosity = resolveVerbosity(ctx.model);
      if (verbosity) {
        const style = getVerbosityStyle(opts);
        parts.push(colorForVerbosity(ctx.theme, verbosity, formatVerbosity(verbosity, style)));
      }

      if (isFastEnabled(ctx.model)) {
        parts.push(colorForFast(ctx.theme, formatFast(getFastStyle(opts))));
      }

      return {
        content: parts.join(" "),
        visible: true,
      };
    },
  };

  registerSegment(segment);
}
