import { formatWhen } from "@/lib/format";
import { companyRepository } from "@/lib/state";

export const dynamic = "force-dynamic";

export default async function ControlPage() {
  const state = await companyRepository().load();
  const latest = [...state.controlTicks]
    .filter((tick) => tick.tickType === "queue_health")
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))[0];
  const notifications = [...state.ownerNotifications]
    .filter((notification) => notification.status === "pending")
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));

  return (
    <>
      <h2>Hosted control</h2>
      <p className="deck">
        Lightweight scheduling and queue health continue in Postgres while
        owner computers sleep. Heavy work still waits for a compatible trusted
        worker.
      </p>

      {latest === undefined ? (
        <p className="deck">The first hosted control tick has not run yet.</p>
      ) : (
        <>
          <div className="stats">
            <div className="stat">
              <b>{latest.metrics.onlineWorkers}</b>
              <span>Workers online</span>
            </div>
            <div className="stat">
              <b>{latest.metrics.queuedTasks}</b>
              <span>Queued tasks</span>
            </div>
            <div className="stat">
              <b>{latest.metrics.incompatibleTasks}</b>
              <span>No compatible worker</span>
            </div>
            <div className="stat">
              <b>{latest.metrics.reclaimedLeaseCount}</b>
              <span>Leases recovered</span>
            </div>
          </div>
          <p className="muted">
            Last control tick {formatWhen(latest.createdAt)}
          </p>
        </>
      )}

      <h2>Owner notices</h2>
      {notifications.length === 0 ? (
        <p className="deck">No hosted-control notice needs attention.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Notice</th>
              <th>Severity</th>
              <th>Detail</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {notifications.map((notification) => (
              <tr key={notification.id}>
                <td>{notification.title}</td>
                <td className={`status status--${notification.severity}`}>
                  {notification.severity}
                </td>
                <td className="muted">{notification.detail}</td>
                <td className="muted">{formatWhen(notification.createdAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Authority boundary</h2>
      <p className="deck">
        Hosted control can expire messages, reclaim dead leases, record health,
        and create reminders. It cannot run a model, edit a repository, approve
        work, merge, deploy, publish, charge, or change the canonical town.
      </p>
    </>
  );
}
