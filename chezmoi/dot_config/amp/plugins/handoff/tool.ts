import type { PluginAPI } from "@ampcode/plugin";
import { z } from "zod";

const HandoffInputSchema = z.object({
  goal: z.string().trim().min(1),
  summary: z.string(),
  relevantFiles: z.array(z.string()),
  nextTask: z.string(),
  openQuestions: z.array(z.string()),
  mode: z.literal("deep").optional(),
  focus: z.boolean().optional().default(false),
});

interface HandoffPromptInput {
  sourceThreadID: string;
  goal: string;
  summary: string;
  relevantFiles: string[];
  nextTask: string;
  openQuestions: string[];
}

function formatList(items: string[]): string {
  return items.map((item) => `- ${item}`).join("\n");
}

function formatValidationError(error: z.ZodError): string {
  return error.issues
    .map((issue) => {
      const path = issue.path.length > 0 ? issue.path.join(".") : "input";
      return `- ${path}: ${issue.message}`;
    })
    .join("\n");
}

function buildHandoffPrompt(input: HandoffPromptInput): string {
  return `Continuing work from thread ${input.sourceThreadID}. When you lack specific information, use read_thread to get more information from the parent thread.

Goal:
${input.goal}

## Task
${input.nextTask}

## Relevant Files
${formatList(input.relevantFiles)}

## Context
${input.summary}

## Open Questions
${formatList(input.openQuestions)}`.trim();
}

export function registerHandoffTool(amp: PluginAPI): void {
  amp.registerTool({
    name: "handoff",
    description:
      "Start a new Amp thread for handing off a task from the current thread. Use when the user asks to hand off work, move to a new thread, start fresh, or start parallel/background work. If needed, gather any more context or ask follow up questions before calling this tool to best prepare the new thread for its task.",
    inputSchema: {
      type: "object",
      properties: {
        goal: {
          type: "string",
          minLength: 1,
          description:
            "The goal/task the new thread should accomplish, in one to two concise sentences.",
        },
        summary: {
          type: "string",
          description:
            "Context relevant to the new thread: decisions, current state, constraints, and anything already tried.",
        },
        relevantFiles: {
          type: "array",
          items: { type: "string" },
          description:
            "Relevant file paths for the new thread. If within the current workspace, relative to cwd; if external, absolute path.",
        },
        nextTask: {
          type: "string",
          description:
            "The concrete next action the new thread should take. Usually the user's requested goal sharpened with current context.",
        },
        openQuestions: {
          type: "array",
          items: { type: "string" },
          description:
            "Unresolved questions that materially affect the new thread. Use an empty array when there are none.",
        },
        mode: {
          type: "string",
          enum: ["deep"],
          description:
            "Optional target mode for the new thread's agent. Leave blank unless the user explicitly asks for a specific one",
        },
        focus: {
          type: "boolean",
          description:
            "When true, replace this current thread with the new handoff thread. When false, start the new thread in the background. Use context clues to determine if the new thread should be focused.",
        },
      },
      required: ["goal", "summary", "relevantFiles", "nextTask", "openQuestions"],
      additionalProperties: false,
    },
    async execute(input, ctx) {
      const result = HandoffInputSchema.safeParse(input);
      if (!result.success) {
        return `Invalid handoff input:\n${formatValidationError(result.error)}`;
      }

      const handoff = result.data;
      const sourceThreadID = ctx.thread.id;
      const handoffPrompt = buildHandoffPrompt({
        sourceThreadID,
        goal: handoff.goal,
        summary: handoff.summary,
        relevantFiles: handoff.relevantFiles,
        nextTask: handoff.nextTask,
        openQuestions: handoff.openQuestions,
      });

      const targetAgent =
        handoff.mode === "deep" ? amp.getBuiltinAgent("deep") : await ctx.thread.agent();
      const newThread = await targetAgent.createThread({
        parentThreadID: sourceThreadID,
        show: handoff.focus,
      });

      await newThread.appendUserMessage({
        type: "user-message",
        content: handoffPrompt,
      });

      return `Created handoff thread ${newThread.id} for goal: ${handoff.goal}`;
    },
  });
}
