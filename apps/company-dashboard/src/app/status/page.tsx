const ROWS: readonly (readonly [string, string, string])[] = [
  ["Domain contracts and policy kernel", "implemented", "28 core tests; strict TypeScript"],
  ["Deterministic goal simulation", "implemented", "Runs from the Goals page; zero side effects"],
  ["Owner approval decisions", "implemented", "Digest-pinned kernel; owner-role enforcement"],
  ["Dashboard persistence", "simulated", "Local JSON store; Supabase adapter replaces it"],
  ["Development database", "implemented", "Migration applied to followville-company-os-dev and verified isolated"],
  ["Dashboard → Supabase adapter", "planned", "Next task: replace the JSON store with the dev database"],
  ["Owner sign-in", "planned", "Supabase Auth against the dev project, replacing the local owner picker"],
  ["Real coding worker + reviewer", "planned", "Phase 2, draft PRs only"],
  ["Durable scheduling and events", "planned", "Phase 3, Inngest pilot"],
  ["Model providers and cost ledger", "planned", "Phase 4; $0 budget until configured"],
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
