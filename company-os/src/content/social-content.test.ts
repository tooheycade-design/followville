import assert from "node:assert/strict";
import test from "node:test";

import {
  buildContentProductionInitiative,
  buildSocialContentPacket,
  selectedConcept,
} from "./social-content.js";

const ids = [
  "81000000-0000-4000-8000-000000000001",
  "81000000-0000-4000-8000-000000000002",
  "81000000-0000-4000-8000-000000000003",
  "81000000-0000-4000-8000-000000000004",
];

function packet() {
  let cursor = 0;
  return buildSocialContentPacket({
    createdByUserId: "30000000-0000-4000-8000-000000000001",
    milestone: { day: 24, population: 412, buildingCount: 415, seedCounter: 415 },
    sourceSnapshotIds: ["82000000-0000-4000-8000-000000000001"],
    sourceDigest: "a".repeat(64),
    engagementDataStatus: "setup_required",
    priorContentNotes: ["Overhead reveals have been used before."],
    idFactory: () => ids[cursor++]!,
    now: "2026-07-29T12:00:00.000Z",
  });
}

test("builds three distinct, source-backed concepts without invented metrics", () => {
  const result = packet();
  assert.deepEqual(
    result.concepts.map((concept) => concept.format),
    ["milestone_reveal", "town_story", "community_prompt"],
  );
  assert.equal(result.milestone.day, 24);
  assert.equal(result.milestone.population, 412);
  assert.equal(result.engagementDataStatus, "setup_required");
  assert.match(result.dataGaps.join(" "), /not connected/i);
  assert.doesNotMatch(JSON.stringify(result), /\b\d+(\.\d+)?%\b/);
});

test("rejects a concept that is not part of the packet", () => {
  assert.throws(
    () => selectedConcept(packet(), "83000000-0000-4000-8000-000000000099"),
    /does not belong/,
  );
});

test("stale engagement is disclosed without pretending it is disconnected", () => {
  let cursor = 0;
  const result = buildSocialContentPacket({
    createdByUserId: "30000000-0000-4000-8000-000000000001",
    milestone: { day: 24, population: 412, buildingCount: 415, seedCounter: 415 },
    sourceSnapshotIds: ["82000000-0000-4000-8000-000000000001"],
    sourceDigest: "c".repeat(64),
    engagementDataStatus: "stale",
    priorContentNotes: [],
    idFactory: () => ids[cursor++]!,
    now: "2026-07-29T12:00:00.000Z",
  });
  assert.match(result.dataGaps.join(" "), /no fresh confirmed snapshot/i);
  assert.doesNotMatch(result.dataGaps.join(" "), /not connected/i);
});

test("production initiative is private, bounded, and review-gated", () => {
  const result = packet();
  const initiative = buildContentProductionInitiative({
    packet: result,
    conceptId: result.concepts[0]!.id,
    ownerUserId: result.createdByUserId,
    goalId: "84000000-0000-4000-8000-000000000001",
    taskId: "84000000-0000-4000-8000-000000000002",
    criterionIds: [
      "84000000-0000-4000-8000-000000000003",
      "84000000-0000-4000-8000-000000000004",
      "84000000-0000-4000-8000-000000000005",
      "84000000-0000-4000-8000-000000000006",
    ],
    now: result.createdAt,
  });
  assert.equal(initiative.task.approvalRequired, true);
  assert.ok(initiative.task.allowedCapabilities.includes("blender_preview"));
  assert.ok(!initiative.task.allowedCapabilities.includes("social_publish"));
  assert.ok(!initiative.task.allowedCapabilities.includes("public_communication"));
  assert.deepEqual(
    initiative.task.repositoryScopes[0]?.allowedPathPrefixes,
    ["company-os/content", "company-os/candidates/cinematic"],
  );
  assert.match(initiative.task.objective, /Do not[\s\S]*world_state\.json/);
});
