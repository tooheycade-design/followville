import { createHash, randomUUID } from "node:crypto";

import {
  buildContentProductionInitiative,
  buildSocialContentPacket,
  SocialContentPacketSchema,
  type SocialContentPacket,
} from "@followville/company-os-core";

import type { CompanyRepository, CompanyState } from "./state/types";

function metric(
  metrics: Record<string, string | number | boolean | null>,
  key: string,
): number {
  const value = metrics[key];
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new Error(`The latest town snapshot has no valid ${key}.`);
  }
  return value;
}

export async function createContentPacket(input: {
  ownerUserId: string;
  objective?: string;
  repository: CompanyRepository;
  idFactory?: () => string;
  now?: string;
}): Promise<SocialContentPacket> {
  const state = await input.repository.load();
  const townSource = state.integrationSources.find(
    (source) => source.sourceKey === "public_town_state",
  );
  if (townSource === undefined) {
    throw new Error("The public town-state source is not configured.");
  }
  const snapshot = state.operationalSnapshots
    .filter(
      (candidate) =>
        candidate.sourceId === townSource.id &&
        candidate.confidence === "confirmed",
    )
    .sort((left, right) => right.capturedAt.localeCompare(left.capturedAt))[0];
  if (snapshot === undefined) {
    throw new Error("Refresh Operations before creating a content packet.");
  }

  const instagram = state.integrationSources.find(
    (source) => source.sourceType === "instagram",
  );
  const engagementSnapshot =
    instagram === undefined
      ? undefined
      : state.operationalSnapshots
          .filter(
            (candidate) =>
              candidate.sourceId === instagram.id &&
              candidate.confidence === "confirmed",
          )
          .sort((left, right) =>
            right.capturedAt.localeCompare(left.capturedAt),
          )[0];
  const nowMs = Date.parse(input.now ?? new Date().toISOString());
  const engagementDataStatus =
    instagram?.status === "active" &&
    engagementSnapshot !== undefined &&
    Date.parse(engagementSnapshot.freshnessUntil) > nowMs
      ? "available"
      : instagram?.status === "active" || instagram?.status === "degraded"
        ? "stale"
        : "setup_required";
  const memories = await input.repository.retrieveMemories(
    "content",
    "Instagram Reel milestone previous content Followville",
    ["content", "milestone"],
    8,
  );
  const idFactory = input.idFactory ?? randomUUID;
  const packet = buildSocialContentPacket({
    createdByUserId: input.ownerUserId,
    objective: input.objective,
    milestone: {
      day: metric(snapshot.metrics, "day"),
      population: metric(snapshot.metrics, "population"),
      buildingCount: metric(snapshot.metrics, "buildingCount"),
      seedCounter: metric(snapshot.metrics, "seedCounter"),
    },
    sourceSnapshotIds: [
      snapshot.id,
      ...(engagementSnapshot === undefined ? [] : [engagementSnapshot.id]),
    ],
    sourceDigest: createHash("sha256")
      .update(
        [snapshot.sourceDigest, engagementSnapshot?.sourceDigest]
          .filter((value): value is string => value !== undefined)
          .join(":"),
        "utf8",
      )
      .digest("hex"),
    engagementDataStatus,
    priorContentNotes: memories.map(
      (memory) => `${memory.subject}: ${memory.body}`,
    ),
    idFactory,
    now: input.now,
  });
  return input.repository.recordContentPacket(packet);
}

export function prepareContentSelection(input: {
  state: CompanyState;
  packetId: string;
  conceptId: string;
  expectedVersion: number;
  ownerUserId: string;
  idFactory?: () => string;
  now?: string;
}) {
  const packet = input.state.contentPackets.find(
    (candidate) => candidate.id === input.packetId,
  );
  if (packet === undefined) {
    throw new Error("Content packet not found.");
  }
  SocialContentPacketSchema.parse(packet);
  if (packet.status !== "draft") {
    throw new Error("This packet already has a selected concept.");
  }
  if (packet.version !== input.expectedVersion) {
    throw new Error("The packet changed after it was opened. Reload it first.");
  }
  const id = input.idFactory ?? randomUUID;
  const { goal, task } = buildContentProductionInitiative({
    packet,
    conceptId: input.conceptId,
    ownerUserId: input.ownerUserId,
    goalId: id(),
    taskId: id(),
    criterionIds: [id(), id(), id(), id()],
    now: input.now,
  });
  const decisionDigest = createHash("sha256")
    .update(
      `${packet.id}:${packet.version}:${input.conceptId}:${packet.sourceDigest}`,
      "utf8",
    )
    .digest("hex");
  return {
    packetId: packet.id,
    conceptId: input.conceptId,
    expectedVersion: packet.version,
    decisionDigest,
    goal,
    task,
  };
}
