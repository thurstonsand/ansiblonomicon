import type { CompanionStatusLabel } from "./status.js";

export interface CompanionTheme {
  pillBg: string;
  border: string;
  shadow: string;
  divider: string;
  text: string;
  muted: string;
  subtle: string;
  separator: string;
  attentionDot: string;
  attentionGlow: string;
  attentionPulse: string;
  dots: Record<string, string>;
}

export interface CompanionUpdateMessage {
  id: string;
  project?: string;
  status?: CompanionStatusLabel;
  detail?: string;
  contextPercent?: number;
  attention?: boolean;
  attentionLabel?: string;
  acknowledgementPending?: boolean;
  theme?: CompanionTheme;
  type?: string;
}

export interface CompanionRemoveMessage {
  id: string;
  type: "remove";
}

export type CompanionMessage = CompanionUpdateMessage | CompanionRemoveMessage;
