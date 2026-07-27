import { decodeWorkerReport } from "@followville/company-os-core";

import { companyRepository } from "@/lib/state";
import { formatWhen, label, shortId } from "@/lib/format";

export const dynamic = "force-dynamic";

/**
 * What to show in a table cell for a reason that may be a whole work report.
 *
 * A worker's reason now carries its full narrative and the diff it produced,
 * because the Chief Executive has to judge on those. A table wants one line, so
 * this shows the opening of the report and says how much more there is rather
 * than pouring a diff into a row and making the trail unscannable.
 */
function reasonSummary(reason: string): string {
  const report = decodeWorkerReport(reason);
  const [first = ""] = report.summary.split("\n");
  const extraLines = report.summary.split("\n").length - 1;
  const parts: string[] = [];
  if (extraLines > 0) {
    parts.push(`+${extraLines} more line(s)`);
  }
  if (report.filesChanged.length > 0) {
    parts.push(`${report.totalFilesChanged} file(s)`);
  }
  if (report.diff !== null) {
    parts.push(report.diffTruncated ? "diff (partial)" : "diff");
  }
  return parts.length > 0 ? `${first}  [${parts.join(", ")}]` : first;
}

export default async function AuditPage() {
  const state = await companyRepository().load();

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
                <td className="muted" title={event.reason}>
                  {reasonSummary(event.reason)}
                </td>
                <td className="mono muted">{shortId(event.requestDigest)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
