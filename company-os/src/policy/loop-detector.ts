export class LoopDetector {
  readonly #counts = new Map<string, number>();

  constructor(private readonly maxRepeats: number) {
    if (!Number.isInteger(maxRepeats) || maxRepeats < 1) {
      throw new Error("maxRepeats must be a positive integer");
    }
  }

  record(fingerprint: string): { blocked: boolean; count: number } {
    const count = (this.#counts.get(fingerprint) ?? 0) + 1;
    this.#counts.set(fingerprint, count);
    return { blocked: count > this.maxRepeats, count };
  }
}
