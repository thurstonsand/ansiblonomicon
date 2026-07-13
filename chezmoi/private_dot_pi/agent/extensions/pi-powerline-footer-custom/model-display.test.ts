import assert from "node:assert/strict";
import { test } from "node:test";
import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import { updateModelDisplayStatus } from "./model-display.js";

test("renders max thinking with the fourth exponent", () => {
  let status: [key: string, value: string] | undefined;
  const ctx = {
    model: {
      id: "gpt-5.6",
      name: "GPT-5.6",
      provider: "openai",
    },
    ui: {
      setStatus(key: string, value: string) {
        status = [key, value];
      },
      theme: {
        fg(color: string, text: string) {
          return `${color}:${text}`;
        },
      },
    },
  } as unknown as ExtensionContext;

  updateModelDisplayStatus(ctx, "max", undefined);

  assert.deepEqual(status, ["model_display", "text:❁ GPT 5.6⁴"]);
});
