/**
 * Seeds a DEVELOPMENT Company OS database with the organization, project, and
 * agent profiles the application expects, then reports what the connection can
 * see. Idempotent: re-running changes nothing.
 *
 * Run with the environment file so the secret key never appears on a command
 * line or in shell history:
 *
 *   pnpm --dir apps/company-dashboard seed:dev
 *
 * Refuses to run against anything but a Supabase-backed repository.
 */
import { createClient } from "@supabase/supabase-js";

import {
  ORGANIZATION_ID,
  PROJECT_ID,
  SEED_AGENTS,
} from "@followville/company-os-core";

const url = process.env.SUPABASE_URL;
const secretKey = process.env.SUPABASE_SECRET_KEY;

if (url === undefined || secretKey === undefined) {
  console.error(
    "SUPABASE_URL and SUPABASE_SECRET_KEY must be set. Copy .env.example to .env.local and fill it in.",
  );
  process.exit(1);
}

const client = createClient(url, secretKey, {
  db: { schema: "company_ops" },
  auth: { persistSession: false, autoRefreshToken: false },
});

function check(label: string, error: { message: string } | null): void {
  if (error !== null) {
    console.error(`FAILED ${label}: ${error.message}`);
    process.exit(1);
  }
  console.log(`ok    ${label}`);
}

check(
  "organization",
  (
    await client.from("organizations").upsert(
      {
        id: ORGANIZATION_ID,
        slug: "followville",
        name: "Followville",
        constitution_version: "proposed-v0.1.0",
      },
      { onConflict: "id", ignoreDuplicates: true },
    )
  ).error,
);

check(
  "project",
  (
    await client.from("projects").upsert(
      {
        id: PROJECT_ID,
        organization_id: ORGANIZATION_ID,
        slug: "followville-town",
        name: "Followville Town",
        repository: "followville_repo",
      },
      { onConflict: "id", ignoreDuplicates: true },
    )
  ).error,
);

check(
  "agent profiles",
  (
    await client.from("agent_profiles").upsert(
      Object.values(SEED_AGENTS).map((agent) => ({
        id: agent.id,
        organization_id: ORGANIZATION_ID,
        slug: agent.slug,
        name: agent.name,
        role: agent.role,
        profile: agent,
        prompt_version: agent.promptVersion,
      })),
      { onConflict: "id", ignoreDuplicates: true },
    )
  ).error,
);

const counts: Record<string, number> = {};
for (const table of [
  "organizations",
  "projects",
  "agent_profiles",
  "organization_members",
  "goals",
  "tasks",
  "approval_requests",
  "approval_decisions",
  "audit_events",
]) {
  const { count, error } = await client
    .from(table)
    .select("*", { count: "exact", head: true });
  check(`read ${table}`, error);
  counts[table] = count ?? 0;
}

console.log("\nrow counts:", counts);

if (counts.organization_members === 0) {
  console.log(
    "\nNOTE: no owner membership rows yet. Until Cade and Zach each have an\n" +
      "account in this project and an owner row, the approval_decisions trigger\n" +
      "will refuse every decision. See company-os/db/seed/0001_company_seed.sql.",
  );
}
