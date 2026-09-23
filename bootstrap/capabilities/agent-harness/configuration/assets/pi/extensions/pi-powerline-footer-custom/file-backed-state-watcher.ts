import { type FSWatcher, watch } from "node:fs";
import type { Api, Model } from "@earendil-works/pi-ai";

export type Eq<T> = (self: T, that: T) => boolean;

export abstract class FileBackedStateWatcher<TConfig, TValue> {
  private watcher: FSWatcher | undefined;
  private disposed = false;
  private config: TConfig;
  private value: TValue;
  private model: Model<Api>;

  protected constructor(
    private readonly filePath: string,
    model: Model<Api>,
    private readonly onChange: (value: TValue) => void,
    private readonly eq: Eq<TValue>,
  ) {
    this.model = model;
    this.config = this.readConfig();
    this.value = this.project(this.config, this.model);
    this.startWatching();
  }

  get(): TValue {
    return this.value;
  }

  setModel(model: Model<Api>): void {
    if (this.disposed) return;

    this.model = model;
    this.value = this.project(this.config, this.model);
  }

  refreshFromFile(): void {
    if (this.disposed) return;

    this.config = this.readConfig();
    this.recompute();
  }

  dispose(): void {
    if (this.disposed) return;

    this.disposed = true;
    this.watcher?.close();
    this.watcher = undefined;
  }

  protected abstract readConfig(): TConfig;
  protected abstract project(config: TConfig, model: Model<Api>): TValue;

  private recompute(): void {
    const next = this.project(this.config, this.model);
    if (this.eq(next, this.value)) return;

    this.value = next;
    this.onChange(next);
  }

  private startWatching(): void {
    try {
      this.watcher = watch(this.filePath, { persistent: false }, () => {
        if (!this.disposed) this.refreshFromFile();
      });
      this.watcher.on("error", () => this.dispose());
    } catch {
      this.watcher = undefined;
    }
  }
}
