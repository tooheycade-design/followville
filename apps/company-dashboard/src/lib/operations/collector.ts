import { createHash } from "node:crypto";

import type {
  CompanyRepository,
  OperationalSnapshot,
} from "@/lib/state/types";

type Fetch = typeof fetch;

interface AdapterReading {
  sourceKey: string;
  metrics: OperationalSnapshot["metrics"];
  evidenceReference: string;
  sourceDigest: string;
  confidence: OperationalSnapshot["confidence"];
  freshnessMinutes: number;
}

interface ReadOnlyAdapter {
  sourceKey: string;
  read(fetchImpl: Fetch, now: Date): Promise<AdapterReading>;
}

function digest(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function finiteInteger(value: unknown, name: string): number {
  if (
    typeof value !== "number" ||
    !Number.isInteger(value) ||
    value < 0
  ) {
    throw new Error(`invalid_${name}`);
  }
  return value;
}

export class PublicTownStateAdapter implements ReadOnlyAdapter {
  readonly sourceKey = "public_town_state";

  constructor(
    private readonly endpoint =
      process.env.FOLLOWVILLE_PUBLIC_STATE_URL?.trim() ||
      "https://followville-kappa.vercel.app/world_state.json",
  ) {}

  async read(fetchImpl: Fetch): Promise<AdapterReading> {
    const response = await fetchImpl(this.endpoint, {
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) {
      throw new Error(`http_${response.status}`);
    }
    const raw = await response.text();
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const buildings = Array.isArray(parsed.buildings)
      ? parsed.buildings.length
      : -1;
    return {
      sourceKey: this.sourceKey,
      metrics: {
        day: finiteInteger(parsed.day, "day"),
        population: finiteInteger(parsed.pop, "population"),
        buildingCount: finiteInteger(buildings, "buildings"),
        seedCounter: finiteInteger(parsed.seed_counter, "seed_counter"),
      },
      evidenceReference: this.endpoint,
      sourceDigest: digest(raw),
      confidence: "confirmed",
      freshnessMinutes: 30,
    };
  }
}

export class PublicWebsiteHealthAdapter implements ReadOnlyAdapter {
  readonly sourceKey = "public_website_health";

  constructor(
    private readonly endpoint =
      process.env.FOLLOWVILLE_PUBLIC_SITE_URL?.trim() ||
      "https://followville-kappa.vercel.app/",
  ) {}

  async read(fetchImpl: Fetch): Promise<AdapterReading> {
    const started = performance.now();
    const response = await fetchImpl(this.endpoint, {
      cache: "no-store",
      redirect: "follow",
      signal: AbortSignal.timeout(15_000),
    });
    const responseMs = Math.max(0, Math.round(performance.now() - started));
    if (!response.ok) {
      throw new Error(`http_${response.status}`);
    }
    const contentType = response.headers.get("content-type") ?? "unknown";
    return {
      sourceKey: this.sourceKey,
      metrics: {
        reachable: true,
        statusCode: response.status,
        responseMs,
        contentType,
      },
      evidenceReference: response.url || this.endpoint,
      sourceDigest: digest(
        `${response.status}\n${response.url || this.endpoint}\n${contentType}`,
      ),
      confidence: "confirmed",
      freshnessMinutes: 30,
    };
  }
}

export interface OperationalCollectionResult {
  sourceKey: string;
  outcome: "recorded" | "failed";
  detail: string;
}

function failureCode(error: unknown): string {
  const raw = error instanceof Error ? error.message : "unknown_failure";
  const normalized = raw
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 76);
  return normalized.length >= 3 ? normalized : "read_failed";
}

export async function collectReadOnlyOperations(
  repository: CompanyRepository,
  options: {
    fetchImpl?: Fetch;
    now?: Date;
    adapters?: readonly ReadOnlyAdapter[];
  } = {},
): Promise<OperationalCollectionResult[]> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const now = options.now ?? new Date();
  const adapters = options.adapters ?? [
    new PublicTownStateAdapter(),
    new PublicWebsiteHealthAdapter(),
  ];
  const capturedAt = now.toISOString();
  const bucket = Math.floor(now.getTime() / (15 * 60_000));
  const results: OperationalCollectionResult[] = [];

  for (const adapter of adapters) {
    try {
      const reading = await adapter.read(fetchImpl, now);
      await repository.recordOperationalSnapshot({
        ...reading,
        capturedAt,
        idempotencyKey: `${reading.sourceKey}:${bucket}:${reading.sourceDigest}`,
      });
      results.push({
        sourceKey: reading.sourceKey,
        outcome: "recorded",
        detail: "Fresh read-only observation recorded.",
      });
    } catch (error) {
      const code = failureCode(error);
      await repository
        .recordOperationalFailure(adapter.sourceKey, code)
        .catch(() => undefined);
      results.push({
        sourceKey: adapter.sourceKey,
        outcome: "failed",
        detail: code,
      });
    }
  }
  return results;
}
