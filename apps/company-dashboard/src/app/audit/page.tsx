import { readState } from "@/lib/store";
import { formatWhen, label, shortId } from "@/lib/format";

export const dynamic = "force-dynamic";

export default function AuditPage() {
  const state = readState();

  return (
    <>
      <h2>Audit trail</h2>
      <p className="deck">
        Every recorded action, oldest to newest, with request and result
        digests. This is the same append-only shape the database migration
        proposes; nothing here can be edited from the dashboard.
      </p>
      {state.auditEvents.length === 0 ? (
        <p className="deck">No events yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Actor</th>
              <th>Action</th>
              <th>Target</th>
              <th>Outcome</th>
              <th>Reason</th>
              <th>Digest</th>
            </tr>
          </thead>
          <tbody>
            {state.auditEvents.map((event) => (
              <tr key={event.id}>
                <td className="muted">{formatWhen(event.createdAt)}</td>
                <td className="mono">{event.actorType}</td>
                <td>{label(event.action)}</td>
                <td className="mono">
                  {event.targetType} {shortId(event.targetId)}
                </td>
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
                <td className="muted">{event.reason}</td>
                <td className="mono muted">{shortId(event.requestDigest)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
