import {
  createDiagnosticTaskAction,
  refreshOperationsAction,
} from "@/app/actions";
import { formatWhen } from "@/lib/format";
import { companyRepository } from "@/lib/state";

export const dynamic = "force-dynamic";

function metricLabel(name: string): string {
  return name.replace(/([A-Z])/g, " $1").replace(/^./, (value) =>
    value.toUpperCase(),
  );
}

function currentMemoryState(body: string | undefined) {
  if (body === undefined) {
    return null;
  }
  const match = body.match(
    /Day (\d+).*population (\d+).*?(\d+) building records/i,
  );
  return match === null
    ? null
    : {
        day: Number(match[1]),
        population: Number(match[2]),
        buildingCount: Number(match[3]),
      };
}

export default async function OperationsPage() {
  const state = await companyRepository().load();
  const latestBySource = new Map(
    [...state.operationalSnapshots]
      .sort((left, right) => right.capturedAt.localeCompare(left.capturedAt))
      .map((snapshot) => [snapshot.sourceId, snapshot]),
  );
  const publicTown = state.integrationSources.find(
    (source) => source.sourceKey === "public_town_state",
  );
  const publicSnapshot =
    publicTown === undefined ? undefined : latestBySource.get(publicTown.id);
  const memoryState = currentMemoryState(
    state.memories.find(
      (memory) =>
        memory.category === "current_state" && memory.status === "active",
    )?.body,
  );
  const drift =
    publicSnapshot !== undefined &&
    memoryState !== null &&
    (publicSnapshot.metrics.day !== memoryState.day ||
      publicSnapshot.metrics.population !== memoryState.population ||
      publicSnapshot.metrics.buildingCount !== memoryState.buildingCount);
  const configured = state.integrationSources.filter(
    (source) => source.status !== "setup_required",
  ).length;
  const fresh = state.integrationSources.filter((source) => {
    const snapshot = latestBySource.get(source.id);
    return (
      snapshot !== undefined && Date.parse(snapshot.freshnessUntil) > Date.now()
    );
  }).length;
  const openAlerts = state.operationalAlerts.filter(
    (alert) => alert.status === "open",
  );

  return (
    <>
      <h2>Followville operations</h2>
      <p className="deck">
        Read-only product signals. These observations may inform recommendations
        but cannot change production, approve work, or overwrite company memory.
      </p>
      <div className="stats">
        <div className="stat">
          <b>{configured}</b>
          <span>Connected sources</span>
        </div>
        <div className="stat">
          <b>{fresh}</b>
          <span>Fresh now</span>
        </div>
        <div className="stat">
          <b>{state.integrationSources.length - configured}</b>
          <span>Need setup</span>
        </div>
      </div>
      {drift ? (
        <p className="notice notice--error">
          Public town state differs from active project memory. Treat this as
          source drift until the canonical repository is refreshed and memory
          receives a new version.
        </p>
      ) : null}
      {openAlerts.length > 0 ? (
        <section className="operations-alerts" aria-labelledby="alerts-title">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Needs investigation</span>
              <h3 id="alerts-title">Product health alerts</h3>
            </div>
            <span className="status status--blocked">
              {openAlerts.length} open
            </span>
          </div>
          {openAlerts.map((alert) => {
            const marker = `Operational alert ${alert.id}`;
            const diagnostic = state.tasks.find((task) =>
              task.objective.includes(marker),
            );
            return (
              <article className="operation-alert" key={alert.id}>
                <header>
                  <div>
                    <span className="eyebrow">
                      {alert.severity} · {alert.alertKind.replaceAll("_", " ")}
                    </span>
                    <h4>{alert.title}</h4>
                  </div>
                  <span className="muted">{formatWhen(alert.createdAt)}</span>
                </header>
                <p>{alert.detail}</p>
                <p className="muted">{alert.recommendedAction}</p>
                {diagnostic === undefined ? (
                  <form action={createDiagnosticTaskAction}>
                    <input type="hidden" name="alertId" value={alert.id} />
                    <button type="submit">Create diagnostic task</button>
                  </form>
                ) : (
                  <p className="status status--active">
                    Diagnostic task {diagnostic.status.replaceAll("_", " ")}
                  </p>
                )}
              </article>
            );
          })}
        </section>
      ) : null}
      <form action={refreshOperationsAction}>
        <button type="submit">Refresh public signals</button>
      </form>
      <div className="operations-grid">
        {state.integrationSources.map((source) => {
          const snapshot = latestBySource.get(source.id);
          const isFresh =
            snapshot !== undefined &&
            Date.parse(snapshot.freshnessUntil) > Date.now();
          return (
            <article className="operation-source" key={source.id}>
              <header>
                <div>
                  <span className="eyebrow">
                    {source.sourceType.replaceAll("_", " ")}
                  </span>
                  <h3>{source.displayName}</h3>
                </div>
                <span
                  className={`status status--${
                    isFresh ? "active" : source.status
                  }`}
                >
                  {isFresh ? "fresh" : source.status.replaceAll("_", " ")}
                </span>
              </header>
              {snapshot === undefined ? (
                <p className="muted">
                  {source.setupRequirement ??
                    source.lastErrorCode ??
                    "No observation has been recorded yet."}
                </p>
              ) : (
                <>
                  <dl className="operation-metrics">
                    {Object.entries(snapshot.metrics).map(([name, value]) => (
                      <div key={name}>
                        <dt>{metricLabel(name)}</dt>
                        <dd>{String(value)}</dd>
                      </div>
                    ))}
                  </dl>
                  <p className="muted">
                    Captured {formatWhen(snapshot.capturedAt)} · evidence{" "}
                    {snapshot.evidenceReference}
                  </p>
                </>
              )}
            </article>
          );
        })}
      </div>
    </>
  );
}
