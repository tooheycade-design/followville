import assert from "node:assert/strict";
import test from "node:test";

import {
  artifactFromRow,
  messageFromRow,
  runFromRow,
  workerFromRow,
} from "./supabase-repository";

const ID = {
  organization: "10000000-0000-4000-8000-000000000001",
  project: "20000000-0000-4000-8000-000000000001",
  goal: "30000000-0000-4000-8000-000000000001",
  task: "40000000-0000-4000-8000-000000000001",
  run: "50000000-0000-4000-8000-000000000001",
  agent: "60000000-0000-4000-8000-000000000001",
  artifact: "70000000-0000-4000-8000-000000000001",
  message: "80000000-0000-4000-8000-000000000001",
  thread: "90000000-0000-4000-8000-000000000001",
} as const;

const NOW = "2026-07-28T20:00:00.000Z";

test("database run rows do not invent a goal field outside the run contract", () => {
  const run = runFromRow({
    id: ID.run,
    organization_id: ID.organization,
    project_id: ID.project,
    goal_id: ID.goal,
    task_id: ID.task,
    agent_id: ID.agent,
    reviewer_agent_id: null,
    trigger: "schedule",
    mode: "execute",
    status: "running",
    model_provider: "codex",
    model_id: null,
    prompt_version: "v1",
    context_manifest_digest: "a".repeat(64),
    workspace_id: null,
    budget_reservation_usd_micros: 0,
    actual_cost_usd_micros: 0,
    retry_count: 0,
    started_at: NOW,
    completed_at: null,
  });

  assert.equal(run.taskId, ID.task);
  assert.equal("goalId" in run, false);
});

test("database artifact rows retain their required goal scope", () => {
  const artifact = artifactFromRow({
    id: ID.artifact,
    organization_id: ID.organization,
    project_id: ID.project,
    goal_id: ID.goal,
    task_id: ID.task,
    run_id: ID.run,
    kind: "report",
    label: "browser-preview-report.json",
    media_type: "application/json",
    size_bytes: 123,
    sha256: "b".repeat(64),
    location: {
      kind: "object",
      provider: "supabase_storage",
      bucket: "company-os-evidence",
      objectPath:
        `organizations/${ID.organization}/projects/${ID.project}/` +
        `goals/${ID.goal}/tasks/${ID.task}/runs/${ID.run}/` +
        `artifacts/${ID.artifact}/${"b".repeat(64)}`,
    },
    visibility: "owner_only",
    contains_sensitive_data: true,
    safe_to_display: false,
    retention_policy: "approval_record",
    created_by_agent_id: ID.agent,
    created_at: NOW,
    expires_at: null,
  });

  assert.equal(artifact.goalId, ID.goal);
  assert.equal(artifact.runId, ID.run);
});

test("database worker rows retain health and compatibility fields", () => {
  const worker = workerFromRow({
    worker_id: "Cades-Omen-1234",
    organization_id: ID.organization,
    project_id: ID.project,
    agent_id: ID.agent,
    display_name: "Cade's worker",
    machine_name: "Cades-Omen",
    platform: "win32-x64",
    provider: "codex",
    model_id: null,
    software_version: "test",
    capabilities: ["repository_read", "test_execute"],
    status: "online",
    current_task_id: ID.task,
    current_run_id: ID.run,
    metadata: {},
    started_at: NOW,
    last_seen_at: NOW,
  });

  assert.equal(worker.status, "online");
  assert.deepEqual(worker.capabilities, ["repository_read", "test_execute"]);
  assert.equal(worker.currentTaskId, ID.task);
});

test("database message rows unpack bounded structured context", () => {
  const message = messageFromRow({
    id: ID.message,
    organization_id: ID.organization,
    project_id: ID.project,
    goal_id: ID.goal,
    task_id: ID.task,
    thread_id: ID.thread,
    sender_type: "agent",
    sender_id: ID.agent,
    recipient_type: "agent",
    recipient_id: "60000000-0000-4000-8000-000000000002",
    message_type: "review_request",
    priority: "high",
    payload: {
      requestedAction: "Review the checkpoint.",
      contextSummary: "Implementation and focused tests are complete.",
      evidenceArtifactIds: [ID.artifact],
      expectedOutput: "Evidence-backed findings or approval.",
      relatedFiles: ["company-os/src/domain/schemas.ts"],
      relatedCommits: ["a".repeat(40)],
    },
    confidence: "confirmed",
    deadline_at: "2026-07-29T18:00:00.000Z",
    status: "delivered",
    fingerprint: "b".repeat(64),
    created_at: NOW,
    expires_at: "2026-07-30T20:00:00.000Z",
  });

  assert.equal(message.goalId, ID.goal);
  assert.equal(message.contextSummary, "Implementation and focused tests are complete.");
  assert.equal(message.confidence, "confirmed");
  assert.deepEqual(message.evidenceArtifactIds, [ID.artifact]);
});
