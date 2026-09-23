import { readFileSync } from "node:fs";

export type JsonObject = Record<string, unknown>;

export function readJsonFile(filePath: string): JsonObject | undefined {
  try {
    const parsed: unknown = JSON.parse(readFileSync(filePath, "utf8"));
    return isJsonObject(parsed) ? parsed : undefined;
  } catch {
    return undefined;
  }
}

export function isJsonObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
