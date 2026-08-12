/* Runs supabase_migrations/20260810_inventory_system_v1.sql against a real
 * PostgreSQL engine (PGlite, Postgres 18 compiled to wasm) and asserts the
 * behaviour the Inventory System v1 doc promises.
 *
 * This is not a substitute for the rolled-back-transaction rehearsal on the
 * live project that this repo requires before any migration is applied. It is
 * the cheap check that runs first, so an obvious SQL error never reaches a
 * rehearsal against production data.
 *
 *   node --experimental-vm-modules tests/inventory_migration_test.mjs
 *   (needs: npm install @electric-sql/pglite)
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// PGlite is intentionally not a devDependency — see package.json. Fail with the
// fix rather than a bare module-not-found stack.
let PGlite;
try { ({ PGlite } = await import("@electric-sql/pglite")); }
catch {
  console.error("\ninventory migration test needs PGlite, which is not installed.\n" +
                "  pnpm add -D --no-frozen-lockfile @electric-sql/pglite\n");
  process.exit(1);
}

const here = dirname(fileURLToPath(import.meta.url));
const migration = readFileSync(join(here, "..", "supabase_migrations", "20260810_inventory_system_v1.sql"), "utf8");

const db = await new PGlite();
let failures = 0;
const ok = (name, cond, detail = "") => {
  if (cond) console.log(`  pass  ${name}`);
  else { failures++; console.log(`  FAIL  ${name} ${detail}`); }
};
async function throws(sql, params, expected){
  try { await db.query(sql, params); return null; }
  catch (e){ return String(e.message || e).includes(expected) ? expected : `other: ${e.message}`; }
}

/* ── Stand-in for the parts of the live schema the migration depends on ── */
await db.exec(`
  create schema if not exists auth;
  create table if not exists public.profiles (
    user_id uuid primary key,
    instagram_handle text,
    is_admin boolean not null default false,
    verification_status text not null default 'pending',
    avatar jsonb not null default '{"version":1}'::jsonb
  );
  -- settable stand-in for Supabase's auth.uid()
  create or replace function auth.uid() returns uuid
    language sql stable as $$ select nullif(current_setting('test.uid', true),'')::uuid $$;
  do $$ begin
    if not exists (select 1 from pg_roles where rolname='authenticated') then create role authenticated; end if;
    if not exists (select 1 from pg_roles where rolname='anon') then create role anon; end if;
    if not exists (select 1 from pg_roles where rolname='service_role') then create role service_role; end if;
  end $$;
  insert into public.profiles(user_id, instagram_handle)
    values ('11111111-1111-1111-1111-111111111111','zach')
    on conflict do nothing;
`);

/* Existing rows must survive the migration untouched — the whole point of a
   defaulted column. Snapshot before. */
const before = await db.query("select count(*)::int n from public.profiles");

console.log("\napplying migration…");
await db.exec(migration);
console.log("applied.\n");

const after = await db.query("select count(*)::int n from public.profiles");
ok("no profile row added or removed", before.rows[0].n === after.rows[0].n);
ok("existing row backfilled to empty inventory",
  (await db.query("select inventory from public.profiles")).rows[0].inventory.fish &&
  Object.keys((await db.query("select inventory from public.profiles")).rows[0].inventory.fish).length === 0);

const asUser = async () => db.exec(`set test.uid = '11111111-1111-1111-1111-111111111111'`);
const asAnon = async () => db.exec(`set test.uid = ''`);

console.log("\nRPC behaviour");
await asUser();
await db.query(`select public.add_to_my_inventory('{"pond_perch":1}'::jsonb)`);
let inv = (await db.query("select inventory from public.profiles")).rows[0].inventory;
ok("first catch stores count 1", inv.fish.pond_perch === 1, JSON.stringify(inv));

await db.query(`select public.add_to_my_inventory('{"pond_perch":1}'::jsonb)`);
inv = (await db.query("select inventory from public.profiles")).rows[0].inventory;
ok("second identical catch stacks to 2", inv.fish.pond_perch === 2, JSON.stringify(inv));

await db.query(`select public.add_to_my_inventory('{"glass_eel":3,"kaleidoscope_koi":1}'::jsonb)`);
inv = (await db.query("select inventory from public.profiles")).rows[0].inventory;
ok("bulk merge adds multiple species",
  inv.fish.glass_eel === 3 && inv.fish.kaleidoscope_koi === 1 && inv.fish.pond_perch === 2, JSON.stringify(inv));

ok("version stays 1", inv.version === 1);

console.log("\nrejections");
ok("unknown fish id rejected",
  (await throws(`select public.add_to_my_inventory('{"shark":1}'::jsonb)`, [], "bad_inventory")) === "bad_inventory");
ok("zero quantity rejected",
  (await throws(`select public.add_to_my_inventory('{"pond_perch":0}'::jsonb)`, [], "bad_inventory")) === "bad_inventory");
ok("negative quantity rejected",
  (await throws(`select public.add_to_my_inventory('{"pond_perch":-5}'::jsonb)`, [], "bad_inventory")) === "bad_inventory");
ok("fractional quantity rejected",
  (await throws(`select public.add_to_my_inventory('{"pond_perch":1.5}'::jsonb)`, [], "bad_inventory")) === "bad_inventory");
ok("string quantity rejected",
  (await throws(`select public.add_to_my_inventory('{"pond_perch":"9"}'::jsonb)`, [], "bad_inventory")) === "bad_inventory");
ok("per-call total above 200 rejected",
  (await throws(`select public.add_to_my_inventory('{"pond_perch":150,"glass_eel":150}'::jsonb)`, [], "bad_inventory")) === "bad_inventory");
ok("empty payload rejected",
  (await throws(`select public.add_to_my_inventory('{}'::jsonb)`, [], "bad_inventory")) === "bad_inventory");
ok("array payload rejected",
  (await throws(`select public.add_to_my_inventory('[1,2]'::jsonb)`, [], "bad_inventory")) === "bad_inventory");

await asAnon();
ok("signed-out caller rejected",
  (await throws(`select public.add_to_my_inventory('{"pond_perch":1}'::jsonb)`, [], "not_authenticated")) === "not_authenticated");
await asUser();

console.log("\nceiling");
/* 999 is the per-species ceiling: push past it in legal 200-max calls. */
for (let i = 0; i < 6; i++) await db.query(`select public.add_to_my_inventory('{"willow_bass":200}'::jsonb)`);
inv = (await db.query("select inventory from public.profiles")).rows[0].inventory;
ok("count clamps at 999 instead of overflowing", inv.fish.willow_bass === 999, String(inv.fish.willow_bass));

console.log("\nconstraint holds even without the RPC");
ok("direct write of an unknown id blocked by CHECK",
  (await throws(`update public.profiles set inventory = '{"version":1,"fish":{"whale":1}}'::jsonb`, [], "profiles_inventory_valid")) === "profiles_inventory_valid");
ok("direct write of an extra top-level key blocked by CHECK",
  (await throws(`update public.profiles set inventory = '{"version":1,"fish":{},"coins":99}'::jsonb`, [], "profiles_inventory_valid")) === "profiles_inventory_valid");
ok("direct write of wrong version blocked by CHECK",
  (await throws(`update public.profiles set inventory = '{"version":2,"fish":{}}'::jsonb`, [], "profiles_inventory_valid")) === "profiles_inventory_valid");

console.log("\ngrants");
const grants = await db.query(`
  select column_name from information_schema.column_privileges
  where table_schema='public' and table_name='profiles'
    and privilege_type='UPDATE' and grantee='authenticated' order by column_name`);
const cols = grants.rows.map(r => r.column_name).sort();
ok("authenticated may update exactly avatar + inventory",
  JSON.stringify(cols) === JSON.stringify(["avatar","inventory"]), JSON.stringify(cols));
ok("avatar update grant survived the table-wide revoke", cols.includes("avatar"));

const fnGrants = await db.query(`
  select has_function_privilege('anon','public.add_to_my_inventory(jsonb)','execute') a,
         has_function_privilege('authenticated','public.add_to_my_inventory(jsonb)','execute') u`);
ok("anon cannot execute the RPC", fnGrants.rows[0].a === false);
ok("authenticated can execute the RPC", fnGrants.rows[0].u === true);

console.log("\nidempotence");
await db.exec(migration.replace(/^begin;/m, "begin;").replace(/^commit;/m, "commit;"));
inv = (await db.query("select inventory from public.profiles")).rows[0].inventory;
ok("re-running the migration preserves saved fish", inv.fish.pond_perch === 2 && inv.fish.willow_bass === 999);

console.log(failures ? `\n${failures} FAILED\n` : "\nall inventory migration checks passed\n");
process.exit(failures ? 1 : 0);
