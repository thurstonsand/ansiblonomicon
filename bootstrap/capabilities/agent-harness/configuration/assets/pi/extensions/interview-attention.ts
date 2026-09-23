import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const ATTENTION_REQUEST = "glimpseui:attention:request";
const ATTENTION_RESOLVE = "glimpseui:attention:resolve";

export default function interviewAttention(pi: ExtensionAPI): void {
  pi.on("tool_call", (event) => {
    if (event.toolName !== "interview") return;
    pi.events.emit(ATTENTION_REQUEST, { attentionId: event.toolCallId });
  });

  pi.on("tool_execution_end", (event) => {
    if (event.toolName !== "interview") return;
    pi.events.emit(ATTENTION_RESOLVE, { attentionId: event.toolCallId });
  });
}
