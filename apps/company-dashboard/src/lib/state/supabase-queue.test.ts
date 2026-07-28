import assert from "node:assert/strict";
import test from "node:test";

import {
  ORGANIZATION_ID,
  PROJECT_ID,
  SEED_AGENTS,
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
