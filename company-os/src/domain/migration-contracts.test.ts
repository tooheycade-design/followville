import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const migration = (name: string): string =>
  readFileSync(path.join(root, "db", "migrations", name), "utf8");

test("review completion records its owner packet inside the verdict transaction", () => {
  const sql = migration("0013_completed_work_reaches_an_owner.sql");
  const reviewFunction = sql.slice(
    sql.indexOf("create or replace function public.company_os_record_review"),
  );

  assert.match(reviewFunction, /lease_expires_at <= now\(\)/);
  assert.match(
    reviewFunction,
    /perform public\.company_os_record_completed_work\(payload->'completedWork'\)/,
  );
  assert.match(reviewFunction, /set status = v_next_status/);
  assert.ok(
    reviewFunction.indexOf("company_os_record_completed_work") <
      reviewFunction.indexOf("set status = v_next_status"),
  );
});

test("the completed-work helper is not directly callable by service_role", () => {
  const sql = migration("0013_completed_work_reaches_an_owner.sql");

  assert.match(
    sql,
    /revoke all on function public\.company_os_record_completed_work\(jsonb\)\s+from public, anon, authenticated, service_role;/,
  );
  assert.doesNotMatch(
    sql,
    /grant execute on function public\.company_os_record_completed_work/,
  );
});

test("result acceptance and release retain distinct database gates", () => {
  const sql = migration("0014_separate_work_acceptance_from_release.sql");
  const approved = sql.slice(
    sql.indexOf("if new.status = 'approved'"),
    sql.indexOf("if new.status = 'merged'"),
  );
  const merged = sql.slice(
    sql.indexOf("if new.status = 'merged'"),
    sql.indexOf("if new.status = 'deployed'"),
  );

  assert.doesNotMatch(approved, /production_merge/);
  assert.match(merged, /request\.action = 'production_merge'/);
});

test("web identity comes from auth uid and cannot name another user", () => {
  const sql = migration("0016_authenticated_member_identity.sql");

  assert.match(sql, /member\.user_id = \(select auth\.uid\(\)\)/);
  assert.doesNotMatch(sql, /company_os_my_membership\s*\([^)]*uuid/);
  assert.match(
    sql,
    /revoke all on function public\.company_os_my_membership\(\)\s+from public, anon, service_role;/,
  );
  assert.match(
    sql,
    /grant execute on function public\.company_os_my_membership\(\) to authenticated;/,
  );
});

test("an owner request for changes starts a new queued revision atomically", () => {
  const sql = migration("0017_owner_revision_cycle.sql");
  const decisionFunction = sql.slice(
    sql.indexOf("create or replace function public.company_os_record_approval_decision"),
  );

  assert.match(decisionFunction, /d->>'decision' = 'request_changes'/);
  assert.match(decisionFunction, /set status = 'queued'/);
  assert.match(
    decisionFunction,
    /review_cycle_count = review_cycle_count \+ 1/,
  );
  assert.ok(
    decisionFunction.indexOf("insert into company_ops.approval_decisions") <
      decisionFunction.indexOf("set status = 'queued'"),
    "the immutable owner decision must exist before rework is queued",
  );
});

test("worker run completion and task movement share one database transaction", () => {
  const sql = migration("0018_truthful_worker_runs.sql");
  const finish = sql.slice(
    sql.indexOf("create or replace function public.company_os_finish_worker_run"),
  );

  assert.match(finish, /lease_epoch = v_run\.lease_epoch/);
  assert.match(finish, /lease_expires_at > now\(\)/);
  assert.match(finish, /set status = v_task_status::company_ops\.task_status/);
  assert.match(finish, /update company_ops\.runs\s+set status = payload->>'runStatus'/);
  assert.ok(
    finish.indexOf("update company_ops.tasks") <
      finish.indexOf("update company_ops.runs"),
    "the task transition must succeed before the run can claim its final status",
  );
});

test("worker run completion rejects contradictory states and retains unknown models", () => {
  const sql = migration("0019_harden_worker_run_completion.sql");

  assert.match(sql, /worker run status % contradicts task status %/);
  assert.match(sql, /coalesce\(nullif\(payload->>'modelId', ''\), 'unknown'\)/);
  assert.match(sql, /if v_provider is not null then/);
});

test("reviewer-requested revisions become leaseable again atomically", () => {
  const sql = migration("0020_requeue_reviewer_revisions.sql");
  const review = sql.slice(
    sql.indexOf("create or replace function public.company_os_record_review"),
  );

  assert.match(review, /set status = v_next_status/);
  assert.match(review, /set status = 'queued'/);
  assert.match(review, /stored\.action = 'review\.changes_requested'/);
  assert.ok(
    review.indexOf("set status = v_next_status") <
      review.indexOf("set status = 'queued'"),
    "the reviewed rejection must be recorded as changes_requested before requeue",
  );
});

test("automatic revision loops stop after three review cycles", () => {
  const sql = migration("0021_cap_automatic_revision_loops.sql");

  assert.match(sql, /old\.status = 'changes_requested'/);
  assert.match(sql, /new\.status = 'queued'/);
  assert.match(sql, /old\.review_cycle_count >= 3/);
  assert.match(sql, /new\.status := 'failed'/);
  assert.match(sql, /before update on company_ops\.tasks/);
});
