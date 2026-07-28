import assert from "node:assert/strict";
import test from "node:test";

import {
  ORGANIZATION_ID,
  PROJECT_ID,
  SEED_AGENTS,
  type StructuredMessage,
} from "@followville/company-os-core";

import { SupabaseWorkQueue, type WorkerRegistration } from "./supabase-queue";

const NOW = "2026-07-28T20:00:00.000Z";
const worker: WorkerRegistration = {
  workerId: "Cades-Omen-1234",
  organizationId: ORGANIZATION_ID,
  projectId: PROJECT_ID,
  agentId: SEED_AGENTS.engineer.id,
  displayName: "Cade's worker",
  machineName: "Cades-Omen",
  platform: "win32-x64",
  provider: "codex",
  modelId: null,
  softwareVersion: "test",
  capabilities: SEED_AGENTS.engineer.capabilities,
  status: "online",
  metadata: {},
};

test("worker registration uses its service RPC and validates the row", async () => {
  const calls: Array<{ name: string; args: unknown }> = [];
  const queue = new SupabaseWorkQueue({
    async rpc(name: string, args: unknown) {
      calls.push({ name, args });
      return {
        error: null,
        data: {
          worker_id: worker.workerId,
          organization_id: worker.organizationId,
          project_id: worker.projectId,
          agent_id: worker.agentId,
          display_name: worker.displayName,
          machine_name: worker.machineName,
          platform: worker.platform,
          provider: worker.provider,
          model_id: null,
          software_version: worker.softwareVersion,
          capabilities: worker.capabilities,
          status: worker.status,
          current_task_id: null,
          current_run_id: null,
          metadata: {},
          started_at: NOW,
          last_seen_at: NOW,
        },
      };
    },
  } as never);

  const registered = await queue.upsertWorker(worker);

  assert.equal(registered.workerId, worker.workerId);
  assert.deepEqual(calls, [
    {
      name: "company_os_upsert_worker",
      args: { payload: worker },
    },
  ]);
});

test("workers lease only through compatible dispatch", async () => {
  const calls: Array<{ name: string; args: unknown }> = [];
  const queue = new SupabaseWorkQueue({
    async rpc(name: string, args: unknown) {
      calls.push({ name, args });
      return { error: null, data: null };
    },
  } as never);

  assert.equal(await queue.leaseNextTask(worker.workerId, 300), null);
  assert.deepEqual(calls, [
    {
      name: "company_os_lease_next_compatible_task",
      args: { worker_id: worker.workerId, lease_seconds: 300 },
    },
  ]);
});

test("structured messages use the bounded service RPC", async () => {
  const calls: Array<{ name: string; args: unknown }> = [];
  const queue = new SupabaseWorkQueue({
    async rpc(name: string, args: unknown) {
      calls.push({ name, args });
      return { error: null, data: {} };
    },
  } as never);
  const message: StructuredMessage = {
    id: "80000000-0000-4000-8000-000000000001",
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: "30000000-0000-4000-8000-000000000001",
    taskId: "50000000-0000-4000-8000-000000000001",
    threadId: "50000000-0000-4000-8000-000000000001",
    senderType: "agent",
    senderId: SEED_AGENTS.engineer.id,
    recipientType: "agent",
    recipientId: SEED_AGENTS.reviewer.id,
    type: "review_request",
    priority: "normal",
    requestedAction: "Review the checkpoint.",
    contextSummary: "The implementation and checks are complete.",
    evidenceArtifactIds: [],
    expectedOutput: "Evidence-backed findings or approval.",
    deadlineAt: null,
    confidence: "confirmed",
    estimatedCostUsdMicros: 0,
    relatedFiles: [],
    relatedCommits: [],
    status: "created",
    fingerprint: "a".repeat(64),
    createdAt: NOW,
    expiresAt: "2026-08-04T20:00:00.000Z",
  };

  await queue.sendMessage(message);
  assert.deepEqual(calls, [
    {
      name: "company_os_send_message",
      args: { payload: message },
    },
  ]);
});
