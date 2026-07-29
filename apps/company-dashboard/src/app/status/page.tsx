const ROWS: readonly (readonly [string, string, string])[] = [
  ["Domain contracts and policy kernel", "implemented", "226 core and 41 dashboard tests; strict TypeScript"],
  ["Deterministic goal simulation", "implemented", "Runs from the Goals page; zero side effects"],
  ["Owner approval decisions", "implemented", "Digest-pinned kernel; owner-role enforcement"],
  ["Development database", "implemented", "Migration applied to followville-company-os-dev and verified isolated"],
  ["Shared database backend", "implemented", "Verified live: goal, refusal, approval, and audit all recorded transactionally"],
  ["Worker runtime", "implemented", "Registered worker health and agent/capability-compatible multi-machine leasing"],
  ["Worktree isolation", "implemented", "Each task runs in a disposable git worktree; out-of-scope edits fail before review"],
  ["Independent review", "implemented", "A different agent checks evidence before work reaches an owner"],
  ["Real model execution", "implemented", "Codex runs on the ChatGPT plan; Claude Code is optional and needs its own sign-in"],
  ["Owner sign-in", "implemented", "Validated Supabase Auth claims plus active database owner membership; no identity picker"],
  ["Private evidence vault", "implemented", "Run-scoped Supabase Storage; immutable hashes; owner-only expiring links"],
  ["Chief Executive", "implemented", "Plans owner intent into bounded work; cannot widen agent permissions"],
  ["Scheduled wake-ups", "implemented", "Interval-based scheduler with failure backoff; survives machines that sleep"],
  ["Model-backed CEO planning", "implemented", "Provider output is clamped by deterministic capability policy"],
  ["Draft pull requests", "implemented", "Narrow GitHub App; exact checkpoint; draft only; no merge authority"],
  ["Browser preview runtime", "implemented", "Desktop/mobile/town screenshots, traces, console, HTTP, and network checks"],
  ["Worker registry", "implemented", "Cade's worker is live; stale machines age offline; Zach-ready"],
  ["Cost controls", "implemented", "Subscription runs are capped per task and never mislabeled as API spend"],
  ["Blender preview runtime", "implemented", "Isolated GLB/glTF renders and geometry metrics; Cade's Blender 5.1 is live"],
  ["Operating reports", "implemented", "Live daily and seven-day owner report from authoritative control-plane state"],
  ["Social content studio", "implemented", "Snapshot-pinned concepts, owner selection, complete packet, and private preview task; no publisher"],
  ["Followville specialists", "planned", "World QA and town planning; see docs/ROADMAP.md"],
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
