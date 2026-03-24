import path from "node:path";
import { getAgentDir } from "@mariozechner/pi-coding-agent";

const AGENT_DIR = getAgentDir();

export const SEP_DOT = " · ";
export const VERBOSITY_CONFIG_PATH = path.join(AGENT_DIR, "verbosity.json");
export const FAST_CONFIG_BASENAME = "pi-openai-fast.json";
export const FAST_CONFIG_PATH = path.join(AGENT_DIR, "extensions", FAST_CONFIG_BASENAME);
export const VERBOSITY_LEVELS = ["low", "medium", "high"] as const;

export type Verbosity = typeof VERBOSITY_LEVELS[number];
export type VerbosityStyle = "compact" | "labelled" | "icon";
export type FastStyle = "compact" | "labelled" | "icon";
export type VerbosityConfig = Record<string, Verbosity>;

export type FastConfigFile = {
  active?: boolean;
  supportedModels?: string[];
};

export type FastConfig = {
  active: boolean;
  supportedModels: Set<string>;
};

export type ModelSegmentOptions = {
  showThinkingLevel?: boolean;
  verbosity?: {
    style?: VerbosityStyle;
  };
  fast?: {
    style?: FastStyle;
  };
};
