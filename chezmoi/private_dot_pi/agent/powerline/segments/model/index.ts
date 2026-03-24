import type { SegmentContext, SegmentLoaderAPI, StatusLineSegment } from "pi-powerline-footer";
import { SEP_DOT, type ModelSegmentOptions } from "./constants.js";
import { isFastEnabled, getFastStyle, formatFast, colorForFast } from "./fast.js";
import { applyThinkingExponent, stripClaudePrefix } from "./label.js";
import { applyColor, getModelIcon, getThinkingText, withIcon } from "./theme.js";
import { colorForVerbosity, formatVerbosity, getVerbosityStyle, resolveVerbosity } from "./verbosity.js";

export default function ({ registerSegment }: SegmentLoaderAPI): void {
  const segment: StatusLineSegment<ModelSegmentOptions> = {
    id: "model",
    render(ctx: SegmentContext, options) {
      const opts = options ?? ctx.options.model ?? {};

      const rawDisplayName = ctx.activeProfileLabel
        ? ctx.activeProfileLabel
        : stripClaudePrefix(ctx.model?.name || ctx.model?.id || "no-model");

      const displayName = applyThinkingExponent(rawDisplayName, ctx.thinkingLevel);

      let primary = withIcon(getModelIcon(), displayName);

      if (!ctx.activeProfileLabel && opts.showThinkingLevel !== false && ctx.model?.reasoning) {
        const level = ctx.thinkingLevel || "off";
        if (level !== "off") {
          const thinkingText = getThinkingText(level);
          if (thinkingText) {
            primary += `${SEP_DOT}${thinkingText}`;
          }
        }
      }

      if (!ctx.activeProfileLabel && ctx.activeProfileIndex !== null) {
        primary += ` (P${ctx.activeProfileIndex + 1})`;
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
