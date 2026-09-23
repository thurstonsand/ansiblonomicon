import type { PendingResultNote } from "./presentation.ts";

function key(threadID: string, toolUseID: string): string {
  return `${threadID}\0${toolUseID}`;
}

class PendingApprovalNotes {
  private readonly byThreadAndToolUseID = new Map<string, PendingResultNote>();

  remember(threadID: string, toolUseID: string, note: PendingResultNote): void {
    this.byThreadAndToolUseID.set(key(threadID, toolUseID), note);
  }

  consume(threadID: string, toolUseID: string): PendingResultNote | undefined {
    const noteKey = key(threadID, toolUseID);
    const note = this.byThreadAndToolUseID.get(noteKey);
    this.byThreadAndToolUseID.delete(noteKey);
    return note;
  }

  discardForThread(threadID: string): void {
    for (const noteKey of this.byThreadAndToolUseID.keys()) {
      if (noteKey.startsWith(`${threadID}\0`)) {
        this.byThreadAndToolUseID.delete(noteKey);
      }
    }
  }
}

export const pendingApprovalNotes = new PendingApprovalNotes();
