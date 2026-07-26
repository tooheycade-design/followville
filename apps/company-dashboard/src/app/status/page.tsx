const ROWS: readonly (readonly [string, string, string])[] = [
  ["Domain contracts and policy kernel", "implemented", "28 core tests; strict TypeScript"],
  ["Deterministic goal simulation", "implemented", "Runs from the Goals page; zero side effects"],
  ["Owner approval decisions", "implemented", "Digest-pinned kernel; owner-role enforcement"],
  ["Development database", "implemented", "Migration applied to followville-company-os-dev and verified isolated"],
  ["Shared database backend", "implemented", "Verified live: goal, refusal, approval, and audit all recorded transactionally"],
  ["Worker runtime", "implemented", "Leases queued work across machines; verified two workers race and exactly one wins"],
  ["Worktree isolation", "implemented", "Each task runs in a disposable git worktree; out-of-scope edits fail before review"],
  ["Independent review", "implemented", "A different agent checks evidence before work reaches an owner"],
  ["Real model execution", "requires human setup", "Run: claude auth login. Until then the worker uses the deterministic executor"],
  ["Owner sign-in", "planned", "Supabase Auth session, replacing the owner picker; the database already rejects non-owners"],
  ["Chief Executive", "implemented", "Plans owner intent into bounded work; cannot widen agent permissions"],
  ["Scheduled wake-ups", "implemented", "Interval-based scheduler with failure backoff; survives machines that sleep"],
  ["Model-backed CEO planning", "planned", "Same clamping, a real model instead of the heuristic planner"],
  ["Draft pull requests", "planned", "GitHub App so completed work arrives as a reviewable PR"],
  ["Cost ledger", "planned", "Usage is recorded per run; the per-provider ledger and budgets come next"],
  ["Followville specialists", "planned", "World QA, Blender, social drafting; see docs/ROADMAP.md"],
  ["Production merge / deploy / publish", "blocked", "By constitution, owner approval only"],
];

const STATUS_CLASS: Record<string, string> = {
  implemented: "approved",
  simulated: "pending",
  "requires human setup": "pending",
  planned: "neutral",
  blocked: "denied",
};

export default function StatusPage() {
  return (
    <>
      <h2>Build status</h2>
      <p className="deck">
        What is real, what is simulated, and what is deliberately not built
        yet. This page exists so the dashboard never overstates itself.
      </p>
      <table>
        <thead>
          <tr>
            <th>Area</th>
            <th>Status</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map(([area, status, note]) => (
            <tr key={area}>
              <td>{area}</td>
              <td className={`status status--${STATUS_CLASS[status] ?? "neutral"}`}>
                {status}
              </td>
              <td className="muted">{note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
