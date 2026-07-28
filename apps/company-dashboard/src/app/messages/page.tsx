import Link from "next/link";

import { formatWhen } from "@/lib/format";
import { companyRepository } from "@/lib/state";

export const dynamic = "force-dynamic";

function participantName(
  id: string,
  agents: Map<string, string>,
  type: string,
) {
  if (type === "agent") {
    return agents.get(id) ?? `Agent ${id.slice(0, 8)}`;
  }
  return `Owner ${id.slice(0, 8)}`;
}

export default async function MessagesPage() {
  const state = await companyRepository().load();
  const agents = new Map(
    state.tasks.flatMap((task) => {
      const pairs: [string, string][] = [];
      if (task.assignedAgentId !== null) {
        pairs.push([task.assignedAgentId, "Worker"]);
      }
      if (task.reviewerAgentId !== null) {
        pairs.push([task.reviewerAgentId, "Reviewer"]);
      }
      return pairs;
    }),
  );
  const tasks = new Map(state.tasks.map((task) => [task.id, task]));
  const messages = [...state.messages].sort((a, b) =>
    b.createdAt.localeCompare(a.createdAt),
  );
  const unresolved = messages.filter(
    (message) =>
      message.status !== "resolved" && message.status !== "expired",
  ).length;

  return (
    <>
      <h2>Agent messages</h2>
      <p className="deck">
        Bounded requests and evidence passed between workers. Messages provide
        context only; they cannot approve work, grant capabilities, or move a
        task.
      </p>

      <div className="stats">
        <div className="stat">
          <b>{unresolved}</b>
          <span>Open messages</span>
        </div>
        <div className="stat">
          <b>{new Set(messages.map((message) => message.threadId)).size}</b>
          <span>Threads</span>
        </div>
        <div className="stat">
          <b>{messages.filter((message) => message.priority === "urgent").length}</b>
          <span>Urgent</span>
        </div>
      </div>

      {messages.length === 0 ? (
        <p className="deck">
          No structured messages have been recorded yet. Worker handoffs and
          reviews remain visible in Factory and Audit.
        </p>
      ) : (
        <div className="message-feed">
          {messages.map((message) => {
            const task =
              message.taskId === null ? undefined : tasks.get(message.taskId);
            return (
              <article className="message-entry" key={message.id}>
                <header>
                  <div>
                    <b>
                      {participantName(
                        message.senderId,
                        agents,
                        message.senderType,
                      )}{" "}
                      to{" "}
                      {participantName(
                        message.recipientId,
                        agents,
                        message.recipientType,
                      )}
                    </b>
                    <span className="muted">{message.type.replaceAll("_", " ")}</span>
                  </div>
                  <div>
                    <span className={`status status--${message.status}`}>
                      {message.status}
                    </span>
                    <span className="muted">{formatWhen(message.createdAt)}</span>
                  </div>
                </header>
                <p>{message.contextSummary}</p>
                {message.requestedAction === null ? null : (
                  <p>
                    <b>Requested action:</b> {message.requestedAction}
                  </p>
                )}
                <footer>
                  {task === undefined ? (
                    <span className="muted">Company-level message</span>
                  ) : (
                    <Link href={`/factory?task=${task.id}`}>{task.title}</Link>
                  )}
                  <span className="muted">
                    Confidence {message.confidence.replaceAll("_", " ")} ·{" "}
                    {message.evidenceArtifactIds.length} evidence item
                    {message.evidenceArtifactIds.length === 1 ? "" : "s"}
                  </span>
                </footer>
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}
