import Link from "next/link";

import { companyRepository } from "@/lib/state";
import { formatUsdMicros, formatWhen, label, shortId } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const state = await companyRepository().load();
  const pending = state.approvalRequests.filter(
    (request) => request.status === "pending",
  );
  const openTasks = state.tasks.filter(
    (task) =>
      !["approved", "rejected", "merged", "deployed", "canceled"].includes(
        task.status,
      ),
  );
  const totalCost = state.runs.reduce(
    (sum, run) => sum + run.actualCostUsdMicros,
    0,
  );

  return (
    <>
      <h2>Needs your attention</h2>
      <p className="deck">
        Only items waiting on a human owner appear here. Everything else stays
        in the full history.
      </p>
      <div className="stats">
        <div className="stat">
          <b>{pending.length}</b>
          <span>Pending approvals</span>
        </div>
        <div className="stat">
          <b>{state.goals.length}</b>
          <span>Goals</span>
        </div>
        <div className="stat">
          <b>{openTasks.length}</b>
          <span>Open tasks</span>
        </div>
        <div className="stat">
          <b>{formatUsdMicros(totalCost)}</b>
          <span>Model spend</span>
        </div>
      </div>

      {pending.length === 0 ? (
        <p className="deck">
          Nothing is waiting on you. Submit a goal from the{" "}
          <Link href="/goals">Goals</Link> page to run the deterministic
          workflow.
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Request</th>
              <th>Action</th>
              <th>Risk</th>
              <th>Requested</th>
              <th>Expires</th>
            </tr>
          </thead>
          <tbody>
            {pending.map((request) => (
              <tr key={request.id}>
                <td>
                  <Link href="/approvals">{request.summary}</Link>
                  <div className="mono muted">{shortId(request.id)}</div>
                </td>
                <td className="mono">{label(request.action)}</td>
                <td className={`status status--${request.riskLevel === "low" ? "approved" : "pending"}`}>
                  {request.riskLevel}
                </td>
                <td className="muted">{formatWhen(request.createdAt)}</td>
                <td className="muted">{formatWhen(request.expiresAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Recent activity</h2>
      <table>
        <thead>
          <tr>
            <th>When</th>
            <th>Actor</th>
            <th>Event</th>
            <th>Outcome</th>
          </tr>
        </thead>
        <tbody>
          {state.auditEvents
            .slice(-8)
            .reverse()
            .map((event) => (
              <tr key={event.id}>
                <td className="muted">{formatWhen(event.createdAt)}</td>
                <td className="mono">{event.actorType}</td>
                <td>{label(event.action)}</td>
                <td
                  className={`status status--${
                    event.outcome === "succeeded" || event.outcome === "allowed"
                      ? "approved"
                      : event.outcome === "approval_required"
                        ? "pending"
                        : "denied"
                  }`}
                >
                  {label(event.outcome)}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </>
  );
}
