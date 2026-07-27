import { companyRepository } from "@/lib/state";
import { formatWhen, label, shortId } from "@/lib/format";
import { ReleaseForm } from "./release-form";

export const dynamic = "force-dynamic";

/**
 * Work the Chief Executive would not decide alone.
 *
 * The CEO could already recognize risky intent and park it, and told the owner
 * it was waiting for them — but nothing could act on it, so held work simply
 * accumulated. This is the other half: the company can stop unsafe work *and*
 * resume it once a human agrees.
 */
export default async function HeldPage() {
  const state = await companyRepository().load();
  const held = state.tasks.filter((task) => task.status === "proposed");
  const goalsById = new Map(state.goals.map((goal) => [goal.id, goal] as const));
  const decided = state.auditEvents.filter((event) =>
    event.action.startsWith("held_task."),
  );

  return (
    <>
      <h2>Held for your decision</h2>
      <p className="deck">
        The Chief Executive plans work but does not decide anything that is
        yours to decide. These tasks are waiting. Releasing one authorizes
        exactly the capabilities you leave ticked, against the version shown
        here — if the task changes after you read it, the decision is refused
        rather than applied to something you did not review.
      </p>

      {held.length === 0 && <p className="deck">Nothing is held.</p>}

      {held.map((task) => {
        const goal = goalsById.get(task.goalId);
        return (
          <article className="approval" key={task.id}>
            <header>
              <h3>{task.title}</h3>
              <span className="status status--pending">held</span>
            </header>
            <p className="muted">{task.objective}</p>

            <div className="facts">
              <div>
                <b>You asked for</b>
                <span>{goal ? goal.title : shortId(task.goalId)}</span>
              </div>
              <div>
                <b>Why it was held</b>
                <span>
                  {goal && goal.constraints.length > 0
                    ? goal.constraints.join("; ")
                    : "An owner decision is required."}
                </span>
              </div>
              <div>
                <b>Reason given</b>
                <span>{task.reason}</span>
              </div>
              <div>
                <b>Risk</b>
                <span>{label(task.riskLevel)}</span>
              </div>
              <div>
                <b>Capabilities requested</b>
                <span className="mono">
                  {task.allowedCapabilities.map(label).join(", ")}
                </span>
              </div>
              <div>
                <b>Files it may touch</b>
                <span className="mono">
                  {task.repositoryScopes
                    .flatMap((scope) => scope.allowedPathPrefixes)
                    .join(", ") || "none"}
                </span>
              </div>
              <div>
                <b>Never</b>
                <span className="mono">
                  {task.repositoryScopes
                    .flatMap((scope) => scope.deniedPathPrefixes)
                    .join(", ") || "none"}
                </span>
              </div>
              <div>
                <b>Estimated cost</b>
                <span>
                  {task.estimatedCostUsdMicros === 0
                    ? "no metered API spend (subscription)"
                    : `$${(task.estimatedCostUsdMicros / 1_000_000).toFixed(2)}`}
                </span>
              </div>
              <div>
                <b>Version</b>
                <span className="mono">{task.version}</span>
              </div>
            </div>

            <h4>What it must satisfy</h4>
            <ul className="criteria">
              {task.acceptanceCriteria.map((criterion) => (
                <li key={criterion.id}>{criterion.description}</li>
              ))}
            </ul>

            <ReleaseForm
              taskId={task.id}
              expectedVersion={task.version}
              proposedCapabilities={task.allowedCapabilities}
            />
          </article>
        );
      })}

      {decided.length > 0 && (
        <>
          <h2>Decided</h2>
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Decision</th>
                <th>Task</th>
                <th>Outcome</th>
                <th>Comment</th>
              </tr>
            </thead>
            <tbody>
              {[...decided].reverse().map((event) => (
                <tr key={event.id}>
                  <td className="muted">{formatWhen(event.createdAt)}</td>
                  <td>{label(event.action.replace("held_task.", ""))}</td>
                  <td className="mono">{shortId(event.targetId)}</td>
                  <td
                    className={`status status--${
                      event.outcome === "succeeded" ? "approved" : "denied"
                    }`}
                  >
                    {label(event.outcome)}
                  </td>
                  <td className="muted">{event.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}
