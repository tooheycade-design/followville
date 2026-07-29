import assert from "node:assert/strict";
import test from "node:test";

import {
  buildSocialContentPacket,
  ORGANIZATION_ID,
  PROJECT_ID,
} from "@followville/company-os-core";

import { prepareContentSelection } from "./content-studio";
import { emptyState } from "./state/types";

test("selection is version pinned and does not authorize publishing", () => {
  const state = emptyState();
  let cursor = 1;
  const id = () =>
    `91000000-0000-4000-8000-${String(cursor++).padStart(12, "0")}`;
  const packet = buildSocialContentPacket({
    createdByUserId: "30000000-0000-4000-8000-000000000001",
    milestone: { day: 24, population: 412, buildingCount: 415, seedCounter: 415 },
    sourceSnapshotIds: ["92000000-0000-4000-8000-000000000001"],
    sourceDigest: "b".repeat(64),
    engagementDataStatus: "setup_required",
    priorContentNotes: [],
    idFactory: id,
    now: "2026-07-29T12:00:00.000Z",
  });
  state.contentPackets.push(packet);
  assert.throws(
    () =>
      prepareContentSelection({
        state,
        packetId: packet.id,
        conceptId: packet.concepts[0]!.id,
        expectedVersion: 2,
        ownerUserId: packet.createdByUserId,
      }),
    /changed/,
  );
  const selection = prepareContentSelection({
    state,
    packetId: packet.id,
    conceptId: packet.concepts[0]!.id,
    expectedVersion: 1,
    ownerUserId: packet.createdByUserId,
    idFactory: id,
    now: packet.createdAt,
  });
  assert.equal(selection.goal.organizationId, ORGANIZATION_ID);
  assert.equal(selection.task.projectId, PROJECT_ID);
  assert.ok(!selection.task.allowedCapabilities.includes("social_publish"));
});
