import { SEED_AGENTS } from "@followville/company-os-core";

import { formatUsdMicros, label } from "@/lib/format";
import { companyRepository } from "@/lib/state";
import { workerHealth } from "@/lib/worker-health";

export default async function AgentsPage() {
  const agents = Object.values(SEED_AGENTS);
  const state = await companyRepository().load();

  return (
    <>
      <h2>Agent directory</h2>
      <p className="deck">
        Eight least-privilege profiles coordinate planning, implementation,
        technical review, visual review, cost oversight, and reporting. Every profile is
        least-privilege: all budgets are $0 in Phase 1, no profile can write to
        the canonical town files, and production-class capabilities always
        route to a human owner.
      </p>
      <table>
        <thead>
          <tr>
            <th>Agent</th>
            <th>Role</th>
            <th>Model class</th>
            <th>Capabilities</th>
            <th>Task / daily budget</th>
            <th>Needs approval for</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((agent) => (
            <tr key={agent.id}>
              <td>
                <b>{agent.name}</b>
                <div className="muted">{agent.description}</div>
              </td>
              <td className="muted">{agent.role}</td>
              <td className="mono">
                {agent.preferredModelClass}
                <div className="muted">↳ {agent.fallbackModelClass}</div>
              </td>
              <td className="mono">
                {agent.capabilities.map(label).join(", ")}
              </td>
              <td className="mono">
                {formatUsdMicros(agent.maxTaskCostUsdMicros)} /{" "}
                {formatUsdMicros(agent.maxDailyCostUsdMicros)}
              </td>
              <td className="mono">
                {agent.requiresHumanApprovalFor.map(label).join(", ") || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Worker machines</h2>
      <p className="deck">
        Live processes eligible to take work. Compatibility is enforced before
        a task is leased.
      </p>
      {state.workers.length === 0 ? (
        <p className="muted">No worker has registered yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Worker</th>
              <th>Health</th>
              <th>Provider</th>
              <th>Platform</th>
              <th>Capabilities</th>
              <th>Current task</th>
              <th>Last seen</th>
            </tr>
          </thead>
          <tbody>
            {[...state.workers]
              .sort((a, b) => b.lastSeenAt.localeCompare(a.lastSeenAt))
              .map((worker) => {
                const health = workerHealth(worker);
                return (
                  <tr key={worker.workerId}>
                    <td>
                      <b>{worker.displayName}</b>
                      <div className="muted mono">{worker.workerId}</div>
                    </td>
                    <td className={`status status--${health.className}`}>
                      {health.label}
                    </td>
                    <td className="mono">{worker.provider}</td>
                    <td className="muted">
                      {worker.machineName}
                      <div>{worker.platform}</div>
                    </td>
                    <td className="mono">
                      {worker.capabilities.map(label).join(", ")}
                    </td>
                    <td className="mono">
                      {worker.currentTaskId?.slice(0, 8) ?? "-"}
                    </td>
                    <td className="mono">
                      {new Date(worker.lastSeenAt).toLocaleString()}
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      )}
    </>
  );
}
