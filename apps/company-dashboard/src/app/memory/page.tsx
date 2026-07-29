import { companyRepository } from "@/lib/state";

import { CorrectionForm } from "./correction-form";

export const dynamic = "force-dynamic";

export default async function MemoryPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const query = (await searchParams).q?.trim().toLowerCase() ?? "";
  const state = await companyRepository().load();
  const memories = state.memories
    .filter(
      (memory) =>
        memory.status === "active" &&
        (query.length === 0 ||
          `${memory.subject} ${memory.body} ${memory.category} ${memory.tags.join(" ")}`
            .toLowerCase()
            .includes(query)),
    )
    .sort(
      (left, right) =>
        left.category.localeCompare(right.category) ||
        left.subject.localeCompare(right.subject),
    );
  const categories = new Set(memories.map((memory) => memory.category)).size;
  const needsOwner = memories.filter(
    (memory) => memory.confidence === "requires_human_verification",
  ).length;

  return (
    <>
      <h2>Company memory</h2>
      <p className="deck">
        Source-backed facts used by the team. Workers receive a ranked maximum
        of eight relevant records per task; the full ledger is never placed in
        a model prompt.
      </p>
      <div className="stats">
        <div className="stat">
          <b>{memories.length}</b>
          <span>Active facts</span>
        </div>
        <div className="stat">
          <b>{categories}</b>
          <span>Categories</span>
        </div>
        <div className="stat">
          <b>{needsOwner}</b>
          <span>Need owner judgment</span>
        </div>
      </div>
      <form className="memory-search">
        <label className="field">
          Search facts, tags, or categories
          <input name="q" defaultValue={query} />
        </label>
        <button type="submit">Search</button>
      </form>
      <div className="memory-ledger">
        {memories.map((memory) => (
          <article className="memory-entry" key={memory.id}>
            <header>
              <div>
                <span className="eyebrow">
                  {memory.category.replaceAll("_", " ")}
                </span>
                <h3>{memory.subject}</h3>
              </div>
              <span className={`status status--${memory.confidence}`}>
                {memory.confidence.replaceAll("_", " ")}
              </span>
            </header>
            <p>{memory.body}</p>
            <dl className="memory-meta">
              <div>
                <dt>Version</dt>
                <dd>{memory.version}</dd>
              </div>
              <div>
                <dt>Audience</dt>
                <dd>{memory.audienceRoles.join(", ")}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>{memory.sourceReference}</dd>
              </div>
              <div>
                <dt>Tags</dt>
                <dd>{memory.tags.join(", ")}</dd>
              </div>
            </dl>
            <details>
              <summary>Correct this fact</summary>
              <CorrectionForm
                memoryId={memory.id}
                expectedVersion={memory.version}
                currentBody={memory.body}
              />
            </details>
          </article>
        ))}
      </div>
    </>
  );
}
