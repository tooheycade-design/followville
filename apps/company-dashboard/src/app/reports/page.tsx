import Link from "next/link";

import { formatUsdMicros, formatWhen } from "@/lib/format";
import {
  buildOperatingReport,
  type PeriodSummary,
} from "@/lib/operating-report";
import { companyRepository } from "@/lib/state";

export const dynamic = "force-dynamic";

function periodRows(period: PeriodSummary) {
  return [
    ["Goals created", period.goalsCreated],
    ["Work completed", period.workCompleted],
    ["Failures", period.failures],
    ["Owner decisions", period.ownerDecisions],
    ["Draft pull requests", period.draftPullRequests],
  ] as const;
}

export default async function ReportsPage() {
  const report = buildOperatingReport(await companyRepository().load());

  return (
    <>
      <h2>Operating report</h2>
      <p className="deck">
        Live from the control plane at {formatWhen(report.generatedAt)}. Counts
        describe recorded work and decisions, not agent claims.
      </p>

      <div className="stats">
        <div className="stat">
          <b>{report.runningTasks}</b>
          <span>Tasks moving</span>
        </div>
        <div className="stat">
          <b>{report.pendingApprovals + report.heldTasks}</b>
          <span>Owner decisions</span>
        </div>
        <div className="stat">
          <b>{report.blockedTasks}</b>
          <span>Blocked / failed</span>
        </div>
        <div className="stat">
          <b>{report.onlineWorkers}</b>
          <span>Workers online</span>
        </div>
        <div className="stat">
          <b>{formatUsdMicros(report.meteredSpendUsdMicros)}</b>
          <span>Metered API spend</span>
        </div>
      </div>

      <h2>Owner attention</h2>
      {report.attention.length === 0 ? (
        <p className="deck">No decision or recovery work is waiting.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Item</th>
              <th>Type</th>
              <th>Why it matters</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {report.attention.map((item) => (
              <tr key={`${item.kind}:${item.id}`}>
                <td>
                  <Link href={item.href}>{item.title}</Link>
                </td>
                <td
                  className={`status status--${item.kind === "failed" ? "denied" : "pending"}`}
                >
                  {item.kind}
                </td>
                <td className="muted">{item.detail}</td>
                <td className="muted">{formatWhen(item.createdAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="report-periods">
        <section className="report-period">
          <h2>Last 24 hours</h2>
          <dl>
            {periodRows(report.day).map(([name, value]) => (
              <div key={name}>
                <dt>{name}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </section>
        <section className="report-period">
          <h2>Seven-day review</h2>
          <dl>
            {periodRows(report.week).map(([name, value]) => (
              <div key={name}>
                <dt>{name}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>

      <h2>Capacity and usage</h2>
      <table>
        <tbody>
          <tr>
            <th>Subscription-backed model runs</th>
            <td>{report.subscriptionRuns}</td>
            <td className="muted">Tracked as runs, not invented dollar spend.</td>
          </tr>
          <tr>
            <th>Workers online</th>
            <td>{report.onlineWorkers}</td>
            <td className="muted">
              {report.unavailableWorkers} delayed, draining, offline, or in error.
            </td>
          </tr>
          <tr>
            <th>Held work</th>
            <td>{report.heldTasks}</td>
            <td className="muted">Cannot start without an owner release.</td>
          </tr>
        </tbody>
      </table>

      <h2>Risks</h2>
      <ul className="report-risks">
        {report.risks.map((risk) => (
          <li key={risk}>{risk}</li>
        ))}
      </ul>
    </>
  );
}
