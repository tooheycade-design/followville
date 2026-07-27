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
