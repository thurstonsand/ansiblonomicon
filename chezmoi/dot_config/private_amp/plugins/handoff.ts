import type { PluginAPI } from "@ampcode/plugin";
import { registerHandoffTool } from "./handoff/tool.ts";

export default function handoff(amp: PluginAPI) {
  registerHandoffTool(amp);
}
