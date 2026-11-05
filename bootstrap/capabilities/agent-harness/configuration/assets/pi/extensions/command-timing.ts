import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function commandTiming(pi: ExtensionAPI): void {
  const starts = new Map<string, number>();

  pi.on("session_start", () => {
    starts.clear();
  });

  pi.on("tool_call", (event) => {
    if (event.toolName === "bash") starts.set(event.toolCallId, performance.now());
  });

  pi.on("tool_result", (event) => {
    if (event.toolName !== "bash") return;
    const started = starts.get(event.toolCallId);
    starts.delete(event.toolCallId);
    if (started === undefined) return;
    const now = performance.now();
    const seconds = (now - started) / 1000;
    let message = `[command-timing] Shell tool elapsed: ${seconds.toFixed(1)}s (includes hook/approval wait).`;
    if (seconds > 300) {
      message +=
        " Very slow feedback loop: over 5 minutes. Change the iteration strategy before repeating this command.";
    } else if (seconds > 60) {
      message += " Slow feedback loop: over 60 seconds.";
    }
    if (seconds > 60) {
      message +=
        " Find a narrower test, file, or reproduction for the next edit. Keep required full-suite validation for the final check; don't skip verification.";
    }
    return {
      content: [...event.content, { type: "text", text: message }],
      structuredContent: event.structuredContent,
    };
  });
}
