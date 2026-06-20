import type { PluginAPI } from "@ampcode/plugin";
import { registerPermissionCommands, TOGGLE_COMMAND_ID } from "./permission-gate/commands.ts";
import { registerPermissionHooks } from "./permission-gate/hooks.ts";
import { PermissionGateState } from "./permission-gate/state.ts";
import { registerPermissionStatus } from "./permission-gate/status.ts";

export default function permissionGate(amp: PluginAPI) {
  const state = new PermissionGateState();
  const status = registerPermissionStatus(amp, state, TOGGLE_COMMAND_ID);

  registerPermissionCommands(amp, state, status);
  registerPermissionHooks(amp, state, status);
}
