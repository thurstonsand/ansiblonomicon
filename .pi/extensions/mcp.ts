import { hostname } from "node:os";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  if (process.platform === "darwin") {
    pi.registerMcpServer("btt", { url: "http://127.0.0.1:64832/mcp" });
  }
  if (hostname() !== "ML-DFC6YK6VJQ") {
    pi.registerMcpServer("home-assistant", {
      url: "https://fdsnaiutiizykhbtju3uhpmumkqhtmmi.ui.nabu.casa/api/webhook/mcp_51f5eb2b59bda0c5d2dcf0f640901cef",
      headers: {
        Authorization: '!echo Bearer $("$HOME/.local/bin/fnox-host" get HOMEASSISTANT_API_KEY)',
      },
    });
  }
}
