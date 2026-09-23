import { spawn } from "node:child_process";
import { connect, type Socket } from "node:net";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { getCompanionSocketPath } from "../shared/socket-path.js";
import { resolveNode } from "./glimpse-support.js";

const SOCK = getCompanionSocketPath();
const COMPANION_PATH = join(fileURLToPath(new URL("..", import.meta.url)), "companion.ts");

export class CompanionConnection {
  private sock: Socket | null = null;

  get isConnected(): boolean {
    return this.sock != null && !this.sock.destroyed;
  }

  async ensureConnected(): Promise<void> {
    if (this.isConnected) return;

    await this.connectOnce();
    if (this.sock) return;

    const node = resolveNode();
    if (!node) return;
    const child = spawn(node, [COMPANION_PATH], {
      detached: true,
      stdio: "ignore",
      windowsHide: process.platform === "win32",
    });
    child.unref();

    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 100));
      await this.connectOnce();
      if (this.sock) return;
    }
  }

  write(payload: object): void {
    if (!this.sock || this.sock.destroyed) return;
    this.sock.write(`${JSON.stringify(payload)}\n`);
  }

  end(): void {
    if (this.sock && !this.sock.destroyed) this.sock.end();
    this.sock = null;
  }

  private connectOnce(): Promise<void> {
    return new Promise((resolve) => {
      this.sock = connect(SOCK, () => resolve());
      this.sock.on("error", () => {
        this.sock = null;
        resolve();
      });
      this.sock.on("close", () => {
        this.sock = null;
      });
    });
  }
}
