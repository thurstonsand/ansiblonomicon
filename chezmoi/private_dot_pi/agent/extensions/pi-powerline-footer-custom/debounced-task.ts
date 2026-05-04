export class DebouncedTask<T extends NonNullable<unknown>> {
  private timer: NodeJS.Timeout | undefined;
  private value: T | undefined;
  private generation = 0;
  private scheduledGeneration = 0;

  constructor(
    private readonly delayMs: number,
    private readonly run: (value: T) => void,
  ) {}

  schedule(value: T): void {
    this.value = value;
    this.scheduledGeneration = this.generation;

    if (this.timer) return;

    this.timer = setTimeout(() => {
      this.timer = undefined;

      const latestValue = this.value;
      const latestGeneration = this.scheduledGeneration;
      this.value = undefined;

      if (latestValue !== undefined && latestGeneration === this.generation) {
        this.run(latestValue);
      }
    }, this.delayMs);
  }

  flush(value?: T): void {
    this.cancelTimer();

    const latestValue = value ?? this.value;
    this.value = undefined;

    if (latestValue !== undefined) {
      this.run(latestValue);
    }
  }

  reset(): void {
    this.generation++;
    this.cancelTimer();
    this.value = undefined;
  }

  private cancelTimer(): void {
    if (!this.timer) return;
    clearTimeout(this.timer);
    this.timer = undefined;
  }
}
