import os from "node:os";
import path from "node:path";
import { SettingsManager } from "@earendil-works/pi-coding-agent";
import type { KeyId } from "@earendil-works/pi-tui";
import { type Static, Type } from "typebox";
import { parseTypeBoxValue } from "./typebox.js";

const DEFAULT_SHORTCUT = "alt+v";
const DEFAULT_OUTPUT_DIR = "/tmp/pi-paste-file";

const PASTE_FILE_SETTINGS_SCHEMA = Type.Object({
  shortcut: Type.Optional(Type.String()),
  outputDir: Type.Optional(Type.String()),
});

const ROOT_SETTINGS_SCHEMA = Type.Object({
  pasteFile: Type.Optional(PASTE_FILE_SETTINGS_SCHEMA),
});

type PasteFileRawSettings = Static<typeof PASTE_FILE_SETTINGS_SCHEMA>;

export interface PasteFileSettings {
  shortcut: KeyId;
  outputDir: string;
}

function expandHome(rawPath: string): string {
  if (rawPath === "~") {
    return os.homedir();
  }

  if (rawPath.startsWith(`~${path.sep}`) || rawPath.startsWith("~/")) {
    return path.join(os.homedir(), rawPath.slice(2));
  }

  return rawPath;
}

function normalizeOutputDir(value: string | undefined): string {
  const trimmed = value?.trim();
  if (!trimmed) {
    return DEFAULT_OUTPUT_DIR;
  }

  const expanded = expandHome(trimmed);
  if (!path.isAbsolute(expanded)) {
    throw new Error('pasteFile.outputDir must be an absolute path or start with "~/".');
  }

  return path.normalize(expanded);
}

function normalizeShortcut(value: string | undefined): KeyId {
  const trimmed = value?.trim();
  return (trimmed ? trimmed : DEFAULT_SHORTCUT) as KeyId;
}

function loadPasteFileRawSettings(): PasteFileRawSettings {
  const globalSettings = SettingsManager.create(process.cwd()).getGlobalSettings();
  const parsed = parseTypeBoxValue(ROOT_SETTINGS_SCHEMA, globalSettings, "Invalid settings");
  return parsed.pasteFile ?? {};
}

function resolvePasteFileSettings(fileSettings: PasteFileRawSettings): PasteFileSettings {
  return {
    shortcut: normalizeShortcut(fileSettings.shortcut),
    outputDir: normalizeOutputDir(fileSettings.outputDir),
  };
}

export function loadSettings(): PasteFileSettings {
  return resolvePasteFileSettings(loadPasteFileRawSettings());
}
