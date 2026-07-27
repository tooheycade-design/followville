import Link from "next/link";

import {
  SEED_AGENTS,
  type AuditEvent,
  type Run,
  type Task,
} from "@followville/company-os-core";

import { formatWhen, label, shortId } from "@/lib/format";
import { companyRepository } from "@/lib/state";
import { LiveRefresh } from "./live-refresh";

export const dynamic = "force-dynamic";

const STATIONS = [
  {
    id: "intake",
    label: "Intake",
    statuses: ["proposed", "planned", "approved_for_work"],
  },
  {
    id: "queue",
    label: "Queued",
    statuses: ["queued", "assigned"],
  },
  {
    id: "work",
    label: "Working",
    statuses: ["in_progress", "changes_requested"],
  },
  {
    id: "review",
    label: "Review",
    statuses: ["awaiting_review"],
  },
  {
    id: "owner",
    label: "Owner",
    statuses: ["awaiting_human_approval"],
  },
  {
    id: "finished",
    label: "Finished / stopped",
    statuses: [
      "approved",
      "merged",
      "deployed",
      "blocked",
      "failed",
      "rejected",
      "canceled",
    ],
  },
] as const;

const agentNames = new Map(
  Object.values(SEED_AGENTS).map((agent) => [agent.id, agent.name]),
);

function latestEventForTask(
  records: readonly AuditEvent[],
  taskId: string,
): AuditEvent | undefined {
  return [...records].reverse().find((record) => record.taskId === taskId);
}

function taskCard(
  task: Task,
  runs: readonly Run[],
  events: readonly AuditEvent[],
) {
  const run = [...runs].reverse().find((candidate) => candidate.taskId === task.id);
  const event = latestEventForTask(events, task.id);
  const destination =
    task.status === "awaiting_human_approval" ? "/approvals" : "/audit";

  return (
    <article className="factory-task" key={task.id}>
      <div className="factory-task__heading">
        <Link href={destination}>{task.title}</Link>
        <span className={`status status--${task.status}`}>
          {label(task.status)}
        </span>
      </div>
      <dl>
        <div>
          <dt>Worker</dt>
          <dd>
            {task.assignedAgentId === null
              ? "Unassigned"
              : agentNames.get(task.assignedAgentId) ??
                shortId(task.assignedAgentId)}
          </dd>
        </div>
        {task.branchName !== null && (
          <div>
            <dt>Branch</dt>
            <dd className="mono">{task.branchName}</dd>
          </div>
        )}
        {run !== undefined && (
          <div>
            <dt>Run</dt>
            <dd>{label(run.status)}</dd>
          </div>
        )}
      </dl>
      {event !== undefined && (
        <p className="factory-task__event" title={event.reason}>
          {label(event.action)}: {event.reason.split("\n")[0]}
        </p>
      )}
      <time>{formatWhen(task.updatedAt)}</time>
    </article>
  );
}

export default async function FactoryPage() {
  const state = await companyRepository().load();
  const tasks = [...state.tasks].sort((left, right) =>
    right.updatedAt.localeCompare(left.updatedAt),
  );
  const activeCount = tasks.filter((task) =>
    ["queued", "assigned", "in_progress", "awaiting_review"].includes(
      task.status,
    ),
  ).length;
  const waitingCount = tasks.filter(
    (task) => task.status === "awaiting_human_approval",
  ).length;

  return (
    <>
      <div className="factory-header">
        <div>
          <h2>Factory floor</h2>
          <p className="deck">
            Follow every task from intake through work, independent review, and
            owner decision.
          </p>
        </div>
        <LiveRefresh />
      </div>

      <div className="factory-summary">
        <span><b>{activeCount}</b> moving</span>
        <span><b>{waitingCount}</b> waiting on owners</span>
        <span><b>{tasks.length}</b> total tasks</span>
      </div>

      <div className="factory-floor">
        {STATIONS.map((station) => {
          const stationTasks = tasks.filter((task) =>
            (station.statuses as readonly string[]).includes(task.status),
          );
          return (
            <section
              className={`factory-station factory-station--${station.id}`}
              key={station.id}
            >
              <header>
                <h3>{station.label}</h3>
                <span>{stationTasks.length}</span>
              </header>
              <div className="factory-station__tasks">
                {stationTasks.length === 0 ? (
                  <p className="factory-empty">Clear</p>
                ) : (
                  stationTasks.map((task) =>
                    taskCard(task, state.runs, state.auditEvents),
                  )
                )}
              </div>
            </section>
          );
        })}
      </div>
    </>
  );
}
