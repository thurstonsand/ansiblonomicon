import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function commandTiming(pi: ExtensionAPI): void {
  pi.on("tool_result", (event) => {
    if (event.toolName !== "bash") return;
    // Pi's bash tool starts this clock at spawn, after permission prompts resolve.
    const seconds = (event.structuredContent as { wall_time_seconds?: number } | undefined)
      ?.wall_time_seconds;
    if (seconds === undefined || seconds <= 60) return;
    let message = `[command-timing] Shell execution took ${seconds.toFixed(1)}s.`;
    message +=
      seconds > 300
        ? " Very slow feedback loop: over 5 minutes. Change the iteration strategy before repeating this command."
        : " Slow feedback loop: over 60 seconds.";
    message +=
      " Find a narrower test, file, or reproduction for the next edit. Keep required full-suite validation for the final check; don't skip verification.";
    pi.sendMessage(
      { customType: "command-timing", content: message, display: false },
      { deliverAs: "steer" },
    );
  });
}
