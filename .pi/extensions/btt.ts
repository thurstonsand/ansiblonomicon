import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  if (process.platform === "darwin") {
    pi.registerMcpServer("btt", { url: "http://127.0.0.1:64832/mcp" });
  }
}
