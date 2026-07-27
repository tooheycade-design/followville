import { companyRepository } from "@/lib/state";
import { ownerName } from "@/lib/config";
import { formatUsdMicros, formatWhen, label, shortId } from "@/lib/format";
import { DecisionForm } from "./decision-form";

export const dynamic = "force-dynamic";

export default async function ApprovalsPage() {
  const state = await companyRepository().load();
  const pending = state.approvalRequests.filter(
    (request) => request.status === "pending",
  );
  const resolved = state.approvalRequests.filter(
    (request) => request.status !== "pending",
  );
  const tasksById = new Map(state.tasks.map((task) => [task.id, task] as const));
  const artifactsById = new Map(
    state.evidenceArtifacts.map((artifact) => [artifact.id, artifact] as const),
  );

  return (
    <>
      <h2>Approval queue</h2>
      <p className="deck">
        A decision is recorded against the exact scope digest shown on this
        page. If the underlying request changes after you read it, the decision
        kernel rejects the stale decision instead of applying it.
      </p>

      {pending.length === 0 && <p className="deck">The queue is empty.</p>}

      {pending.map((request) => {
        const task = tasksById.get(request.taskId);
        return (
          <article className="approval" key={request.id}>
            <header>
              <h3>{request.summary}</h3>
              <span className="status status--pending">pending</span>
            </header>
            <p className="muted">{request.reason}</p>
            <div className="facts">
              <div>
                <b>Action</b>
                <span className="mono">{label(request.action)}</span>
              </div>
              <div>
                <b>Task</b>
                <span>{task ? task.title : shortId(request.taskId)}</span>
              </div>
              <div>
                <b>Risk / reversible</b>
                <span>
                  {request.riskLevel} · {request.reversible ? "yes" : "no"}
                </span>
              </div>
              <div>
                <b>Estimated cost</b>
                <span>{formatUsdMicros(request.estimatedCostUsdMicros)}</span>
              </div>
              <div>
                <b>Tests completed</b>
                <span>{request.testsCompleted.join(", ") || "none"}</span>
              </div>
              <div>
                <b>Recommendation</b>
                <span>{label(request.recommendation)}</span>
              </div>
              <div>
                <b>Approvals needed</b>
                <span>
                  {request.requiredApprovals} ({request.requiredRole})
                </span>
              </div>
              <div>
                <b>Expires</b>
                <span>{formatWhen(request.expiresAt)}</span>
              </div>
              <div>
                <b>Rollback plan</b>
                <span>{request.rollbackPlan}</span>
              </div>
              <div>
                <b>Scope digest</b>
                <span className="mono">{shortId(request.scopeDigest)}…</span>
              </div>
            </div>
            {(() => {
              // Evidence the request actually cites, resolved to real rows.
              // `evidenceArtifactIds` was empty on every request until there
              // was somewhere for an artifact to live.
              const cited = request.evidenceArtifactIds
                .map((id) => artifactsById.get(id))
                .filter((artifact) => artifact !== undefined);
              if (cited.length === 0) {
                return null;
              }
              return (
                <>
                  <h4>Evidence</h4>
                  <ul className="criteria">
                    {cited.map((artifact) => (
                      <li key={artifact.id}>
                        <b>{label(artifact.kind)}</b> — {artifact.label}{" "}
                        <span className="muted">
                          ({artifact.mediaType}, {artifact.sizeBytes} bytes)
                        </span>
                        <br />
                        <code className="mono">
                          {artifact.location.kind === "git"
                            ? `git show ${artifact.location.commitSha}:${artifact.location.repositoryPath}`
                            : "held inline with the record"}
                        </code>
                      </li>
                    ))}
                  </ul>
                </>
              );
            })()}
            <DecisionForm
              approvalRequestId={request.id}
              scopeDigest={request.scopeDigest}
            />
          </article>
        );
      })}

      {resolved.length > 0 && (
        <>
          <h2>Resolved</h2>
          <table>
            <thead>
              <tr>
                <th>Request</th>
                <th>Status</th>
                <th>Decided by</th>
                <th>Comment</th>
              </tr>
            </thead>
            <tbody>
              {[...resolved].reverse().map((request) => {
                const decisions = state.approvalDecisions.filter(
                  (decision) => decision.approvalRequestId === request.id,
                );
                const last = decisions[decisions.length - 1];
                return (
                  <tr key={request.id}>
                    <td>{request.summary}</td>
                    <td className={`status status--${request.status}`}>
                      {label(request.status)}
                    </td>
                    <td>
                      {decisions
                        .map((decision) => ownerName(decision.decidedByUserId))
                        .join(", ") || "—"}
                    </td>
                    <td className="muted">{last?.comment ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}
