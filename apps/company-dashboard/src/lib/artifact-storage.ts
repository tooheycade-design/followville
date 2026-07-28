import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";

import { createClient } from "@supabase/supabase-js";
import type {
  ArtifactLocation,
  ArtifactStore,
  ArtifactStoreInput,
  EvidenceArtifact,
} from "@followville/company-os-core";

export const EVIDENCE_BUCKET = "company-os-evidence";
const SIGNED_URL_SECONDS = 10 * 60;

interface StorageError {
  message: string;
}

export interface ArtifactBucketOperations {
  upload(
    objectPath: string,
    body: Uint8Array,
    options: {
      contentType: string;
      upsert: boolean;
      cacheControl: string;
    },
  ): Promise<{ error: StorageError | null }>;
  download(
    objectPath: string,
  ): Promise<{ data: Blob | null; error: StorageError | null }>;
  createSignedUrl(
    objectPath: string,
    expiresIn: number,
  ): Promise<{ data: { signedUrl: string } | null; error: StorageError | null }>;
}

export interface ArtifactStorageClient {
  from(bucket: string): ArtifactBucketOperations;
}

function serverStorageClient(): ArtifactStorageClient | null {
  const url = process.env.SUPABASE_URL;
  const secretKey = process.env.SUPABASE_SECRET_KEY;
  if (!url || !secretKey) {
    return null;
  }
  return createClient(url, secretKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  }).storage as unknown as ArtifactStorageClient;
}

/** A worker can write only below the exact task/run/artifact path it was given. */
export function evidenceObjectPath(input: ArtifactStoreInput): string {
  return [
    "organizations",
    input.task.organizationId,
    "projects",
    input.task.projectId,
    "goals",
    input.task.goalId,
    "tasks",
    input.task.id,
    "runs",
    input.runId,
    "artifacts",
    input.artifactId,
    input.sha256,
  ].join("/");
}

/**
 * Private server-side evidence storage.
 *
 * The secret key never reaches the browser. Object IDs and hashes make paths
 * immutable, and `upsert: false` prevents a retry from replacing evidence.
 */
export class SupabaseArtifactStore implements ArtifactStore {
  constructor(private readonly storage: ArtifactStorageClient) {}

  static fromEnvironment(): SupabaseArtifactStore | null {
    const storage = serverStorageClient();
    return storage === null ? null : new SupabaseArtifactStore(storage);
  }

  async store(input: ArtifactStoreInput): Promise<ArtifactLocation> {
    const objectPath = evidenceObjectPath(input);
    const bytes = await readFile(input.absolutePath);
    if (bytes.byteLength !== input.sizeBytes) {
      throw new Error("Artifact changed while it was being collected.");
    }
    const bucket = this.storage.from(EVIDENCE_BUCKET);
    const { error } = await bucket.upload(
      objectPath,
      bytes,
      {
        contentType: input.mediaType,
        upsert: false,
        cacheControl: "3600",
      },
    );
    if (error !== null && !/already exists|duplicate/i.test(error.message)) {
      throw new Error(`Artifact upload failed: ${error.message}`);
    }
    const downloaded = await bucket.download(objectPath);
    if (downloaded.error !== null || downloaded.data === null) {
      throw new Error(
        `Artifact verification download failed: ${
          downloaded.error?.message ?? "no data"
        }`,
      );
    }
    const stored = Buffer.from(await downloaded.data.arrayBuffer());
    const storedHash = createHash("sha256").update(stored).digest("hex");
    if (stored.byteLength !== input.sizeBytes || storedHash !== input.sha256) {
      throw new Error("Stored artifact does not match the collected evidence.");
    }
    return {
      kind: "object",
      provider: "supabase_storage",
      bucket: EVIDENCE_BUCKET,
      objectPath,
    };
  }
}

/**
 * Creates a short-lived link only while rendering an authenticated owner page.
 * The durable record stores the object path, never a bearer URL.
 */
export async function signedArtifactUrl(
  artifact: EvidenceArtifact,
): Promise<string | null> {
  if (
    artifact.location.kind !== "object" ||
    artifact.visibility !== "owner_only"
  ) {
    return null;
  }
  const storage = serverStorageClient();
  if (storage === null) {
    return null;
  }
  const { data, error } = await storage
    .from(artifact.location.bucket)
    .createSignedUrl(artifact.location.objectPath, SIGNED_URL_SECONDS);
  if (error !== null || data === null) {
    return null;
  }
  return data.signedUrl;
}
