import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import path from "node:path";
import { promisify } from "node:util";

import { z } from "zod";

import type { CompanyRepository } from "@/lib/state/types";

const exec = promisify(execFile);

const MetricsSchema = z
  .object({
    homeReachable: z.boolean(),
    homeStatusCode: z.number().int().nonnegative(),
    homeDomContentLoadedMs: z.number().int().nonnegative(),
    homeLoadMs: z.number().int().nonnegative(),
    townReachable: z.boolean(),
    townStatusCode: z.number().int().nonnegative(),
    townReadyMs: z.number().int().nonnegative(),
    clientErrorCount: z.number().int().nonnegative(),
    failedRequestCount: z.number().int().nonnegative(),
    apiRequestCount: z.number().int().nonnegative(),
    apiAverageMs: z.number().int().nonnegative(),
    apiFailureCount: z.number().int().nonnegative(),
  })
  .strict();

const ProductHealthOutputSchema = z
  .object({
    generatedAt: z.string().datetime({ offset: true }),
    endpoint: z.string().url(),
    metrics: MetricsSchema,
  })
  .strict();

type Execute = (
  executable: string,
  args: readonly string[],
  options: {
    cwd: string;
    env: NodeJS.ProcessEnv;
    timeout: number;
    windowsHide: boolean;
    maxBuffer: number;
  },
) => Promise<{ stdout: string; stderr: string }>;

function safeEnvironment(): NodeJS.ProcessEnv {
  const environment: NodeJS.ProcessEnv = {
    NODE_ENV: process.env.NODE_ENV ?? "production",
  };
  for (const name of [
    "ComSpec",
    "HOME",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "SystemDrive",
    "SystemRoot",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
  ]) {
    if (process.env[name] !== undefined) environment[name] = process.env[name];
  }
  return environment;
}

export async function collectProductHealth(
  repository: CompanyRepository,
  trustedRepositoryRoot: string,
  options: {
    endpoint?: string;
    execute?: Execute;
  } = {},
) {
  const endpoint =
    options.endpoint ??
    (process.env.FOLLOWVILLE_PUBLIC_SITE_URL?.trim() ||
      "https://followville-kappa.vercel.app/");
  const execute = options.execute ?? (exec as Execute);
  const { stdout } = await execute(
    process.execPath,
    [
      path.join(
        trustedRepositoryRoot,
        "company-os",
        "scripts",
        "product-health.mjs",
      ),
      endpoint,
    ],
    {
      cwd: trustedRepositoryRoot,
      env: safeEnvironment(),
      timeout: 150_000,
      windowsHide: true,
      maxBuffer: 1_000_000,
    },
  );
  const output = ProductHealthOutputSchema.parse(JSON.parse(stdout));
  const serialized = JSON.stringify(output.metrics);
  const sourceDigest = createHash("sha256")
    .update(serialized, "utf8")
    .digest("hex");
  const bucket = Math.floor(Date.parse(output.generatedAt) / (60 * 60_000));

  return repository.recordOperationalSnapshot({
    sourceKey: "browser_product_health",
    capturedAt: output.generatedAt,
    metrics: output.metrics,
    evidenceReference: output.endpoint,
    sourceDigest,
    idempotencyKey: `browser_product_health:${bucket}`,
    confidence: "confirmed",
    freshnessMinutes: 120,
  });
}
