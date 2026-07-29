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

test("durable artifacts are private, scope-derived, and immutable", () => {
  const sql = migration("0022_private_durable_artifacts.sql");

  assert.match(sql, /'company-os-evidence',\s*'company-os-evidence',\s*false/);
  assert.doesNotMatch(sql, /create policy/i);
  assert.match(sql, /artifact object path does not match its database scope/);
  assert.match(sql, /artifact creator does not own its run/);
  assert.match(sql, /object artifact requires a durable run/);
  assert.match(sql, /before truncate on company_ops\.evidence_artifacts/);
  assert.match(sql, /visibility := 'owner_only'/);
  assert.match(sql, /new\.contains_sensitive_data := new\.kind in/);
});

test("structured messages carry context but never authority", () => {
  const sql = migration("0026_structured_agent_messages.sql");

  assert.match(sql, /'message_send'::company_ops\.capability = any\(agent\.capabilities\)/);
  assert.match(sql, /message evidence does not belong to its scope/);
  assert.match(sql, /structured message content and scope are immutable/);
  assert.match(sql, /expires_at <= created_at \+ interval '30 days'/);
  assert.match(sql, /on conflict \(thread_id, fingerprint\) do nothing/);
  assert.doesNotMatch(sql, /update company_ops\.tasks\s+set status/i);
  assert.doesNotMatch(sql, /insert into company_ops\.approval_decisions/i);
  assert.doesNotMatch(sql, /allowed_capabilities\s*=/i);
});

test("message deduplication qualifies its payload argument", () => {
  const sql = migration("0027_fix_message_deduplication.sql");

  assert.match(sql, /message\.thread_id = \(\$1->>'threadId'\)::uuid/);
  assert.match(sql, /message\.fingerprint = \$1->>'fingerprint'/);
});

test("hosted control coordinates but cannot execute or approve", () => {
  const sql = migration("0028_always_on_control_service.sql");

  assert.match(sql, /pg_try_advisory_xact_lock/);
  assert.match(sql, /unique \(organization_id, project_id, tick_type, time_bucket\)/);
  assert.match(sql, /company_os_reclaim_expired_leases\(\)/);
  assert.match(sql, /task\.allowed_capabilities <@ worker\.capabilities/);
  assert.match(sql, /cron\.schedule\(/);
  assert.doesNotMatch(sql, /insert into company_ops\.approval_decisions/i);
  assert.doesNotMatch(sql, /set status = 'approved'/i);
  assert.doesNotMatch(sql, /production_deploy|canonical_world_growth|payment_charge/i);
});

test("hosted control history is retained without unbounded dashboard reads", () => {
  const sql = migration("0029_bound_control_history.sql");

  assert.match(sql, /order by created_at desc limit 500/);
  assert.match(sql, /created_at < clock_timestamp\(\) - interval '90 days'/);
  assert.match(sql, /created_at < clock_timestamp\(\) - interval '30 days'/);
  assert.match(sql, /followville-company-os-control-retention/);
});

test("social content remains source-pinned, owner-selected, and unpublished", () => {
  const sql = migration("0036_social_content_studio.sql");

  assert.match(sql, /jsonb_array_length\(concepts\) = 3/);
  assert.match(sql, /content concept decisions are append-only/);
  assert.match(sql, /packet\.version <> \(payload->>'expectedVersion'\)::integer/);
  assert.match(sql, /active owner required/);
  assert.match(sql, /concept digest mismatch/);
  assert.match(sql, /unsafe content production task/);
  assert.match(sql, /enable row level security/);
  assert.match(sql, /grant execute on function public\.company_os_select_content_concept\(jsonb\)\s+to authenticated/);
  assert.doesNotMatch(sql, /grant execute on function .*publish/i);
});

test("social content decision history rejects truncate", () => {
  const sql = migration("0037_harden_social_content_history.sql");

  assert.match(sql, /before truncate on company_ops\.content_concept_decisions/);
  assert.match(sql, /content_packets_project_created_idx/);
});

test("social content selection hashes explicit UTF-8 bytes", () => {
  const sql = migration("0038_fix_content_selection_digest.sql");

  assert.match(sql, /extensions\.digest\(convert_to\(/);
  assert.match(sql, /packet\.version <> \(payload->>'expectedVersion'\)::integer/);
  assert.match(sql, /grant execute on function public\.company_os_select_content_concept\(jsonb\)\s+to authenticated/);
});

test("social content packets follow private production without gaining publish authority", () => {
  const sql = migration("0039_sync_content_packet_lifecycle.sql");

  assert.match(sql, /after update of status on company_ops\.tasks/);
  assert.match(sql, /awaiting_human_approval' then 'ready_for_owner'/);
  assert.match(sql, /new\.status in \('approved', 'merged'\) then 'approved'/);
  assert.match(sql, /status <> 'published'/);
  assert.doesNotMatch(sql, /then 'published'/);
  assert.doesNotMatch(sql, /approval_decisions|social_publish|instagram/i);
});

test("reviewer outages defer the judge without consuming a worker revision", () => {
  const sql = migration("0040_defer_unavailable_visual_reviews.sql");
  const recordReview = sql.slice(
    sql.indexOf("create or replace function public.company_os_record_review"),
    sql.indexOf(
      "create or replace function public.company_os_retry_failed_review",
    ),
  );

  assert.match(sql, /lease_expires_at is null or t\.lease_expires_at <= now\(\)/);
  assert.match(recordReview, /'deferred'/);
  assert.match(recordReview, /v_retry_after < 60 or v_retry_after > 1800/);
  assert.match(recordReview, /set lease_expires_at = now\(\) \+ make_interval/);
  assert.doesNotMatch(
    recordReview.slice(
      recordReview.indexOf("if v_verdict = 'deferred' then"),
      recordReview.indexOf("v_next_status :="),
    ),
    /review_cycle_count/,
  );
  assert.match(sql, /v_latest_visual\.reason not like 'The independent visual review failed:%'/);
  assert.match(sql, /v_audit->>'action' <> 'review\.retry_scheduled'/);
  assert.match(
    sql,
    /revoke all on function public\.company_os_retry_failed_review\(jsonb\)\s+from public, anon, authenticated;/,
  );
});

test("visual work gets a larger but still bounded revision budget", () => {
  const sql = migration("0041_allow_bounded_visual_revision_budget.sql");

  assert.match(sql, /'browser_preview'::company_ops\.capability = any/);
  assert.match(sql, /'blender_preview'::company_ops\.capability = any/);
  assert.match(sql, /then 5\s+else 3/);
  assert.match(sql, /v_task\.review_cycle_count >= 5/);
  assert.match(sql, /v_latest_visual\.action <> 'visual_review\.changes_requested'/);
  assert.match(sql, /v_audit->>'action' <> 'review\.visual_revision_requeued'/);
  assert.doesNotMatch(
    sql,
    /set\s+(allowed_capabilities|status)\s*=\s*'approved'|social_publish|published/i,
  );
  assert.match(
    sql,
    /revoke all on function public\.company_os_resume_bounded_visual_revision\(jsonb\)\s+from public, anon, authenticated;/,
  );
});

test("portrait-manifest repair permits only one final visual revision", () => {
  const sql = migration("0042_include_portrait_evidence_in_visual_review.sql");

  assert.match(sql, /then 6\s+else 3/);
  assert.match(sql, /v_task\.review_cycle_count >= 6/);
  assert.match(sql, /v_latest_visual\.action <> 'visual_review\.changes_requested'/);
  assert.doesNotMatch(
    sql,
    /set\s+(allowed_capabilities|status)\s*=\s*'approved'|social_publish|published/i,
  );
  assert.match(
    sql,
    /revoke all on function public\.company_os_resume_bounded_visual_revision\(jsonb\)\s+from public, anon, authenticated;/,
  );
});
