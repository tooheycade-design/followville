import { SEED_AGENTS } from "@followville/company-os-core";

import { companyRepository } from "@/lib/state";
import { formatWhen, label, shortId } from "@/lib/format";
import { CeoForm } from "./ceo-form";

export const dynamic = "force-dynamic";

export default async function CeoPage() {
  const state = await companyRepository().load();
  const ceo = SEED_AGENTS.ceo;
  const recent = [...state.goals].reverse().slice(0, 10);
  const tasksByGoal = new Map<string, number>();
  for (const task of state.tasks) {
    tasksByGoal.set(task.goalId, (tasksByGoal.get(task.goalId) ?? 0) + 1);
  }

  return (
    <>
      <h2>Direct the company</h2>
      <p className="deck">
        Say what you want in plain language. The Chief Executive turns it into
        bounded tasks and queues them for the workers. It decides what should
        happen; it cannot widen what any agent is allowed to do, and it holds
        anything that is your call rather than deciding it.
      </p>
      <CeoForm />

      <h2>What the CEO will not decide</h2>
      <p className="deck">
        Intent touching these subjects is queued as proposed work and waits for
        you: monetization and pricing, releasing to production, anything
        public, brand and identity, destructive changes, and the canonical
        town.
      </p>

      <h2>Chief Executive</h2>
      <table>
        <thead>
          <tr>
            <th>Capability</th>
            <th>Held</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>May do</td>
            <td className="mono">{ceo.capabilities.map(label).join(", ")}</td>
          </tr>
          <tr>
            <td>Never</td>
            <td className="mono">
              {ceo.prohibitedCapabilities.map(label).join(", ")}
            </td>
          </tr>
          <tr>
            <td>Escalates</td>
            <td className="muted">{ceo.escalationRules.join(" ")}</td>
          </tr>
        </tbody>
      </table>

      <h2>Initiatives</h2>
      {recent.length === 0 ? (
        <p className="deck">Nothing yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Goal</th>
              <th>Status</th>
              <th>Risk</th>
              <th>Tasks</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((goal) => (
              <tr key={goal.id}>
                <td>
                  {goal.title}
                  <div className="mono muted">{shortId(goal.id)}</div>
                </td>
                <td
                  className={`status status--${
                    goal.status === "awaiting_approval" ? "pending" : "neutral"
                  }`}
                >
                  {label(goal.status)}
                </td>
                <td className="muted">{goal.riskLevel}</td>
                <td className="mono">{tasksByGoal.get(goal.id) ?? 0}</td>
                <td className="muted">{formatWhen(goal.createdAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
