import { companyRepository } from "@/lib/state";
import { formatWhen, label, shortId } from "@/lib/format";

import { ContentBriefForm, SelectConceptForm } from "./content-actions";

export const dynamic = "force-dynamic";

export default async function ContentPage() {
  const state = await companyRepository().load();
  const packets = [...state.contentPackets].sort((left, right) =>
    right.createdAt.localeCompare(left.createdAt),
  );
  const taskById = new Map(state.tasks.map((task) => [task.id, task]));
  const artifactsById = new Map(
    state.evidenceArtifacts.map((artifact) => [artifact.id, artifact] as const),
  );

  return (
    <>
      <h2>Content studio</h2>
      <p className="deck">
        Turn a confirmed town milestone into three complete Reel directions.
        Concepts pin their source data, state what engagement data is missing,
        and wait for an owner before any production work begins.
      </p>
      <ContentBriefForm />

      <div className="content-lock">
        <b>Publishing is locked</b>
        <span>
          This studio has no Instagram credential, publish button, scheduler,
          or social_publish grant. A future publisher remains a separate
          high-risk owner approval.
        </span>
      </div>

      <h2>Packets</h2>
      {packets.length === 0 ? (
        <p className="deck">No content packets yet.</p>
      ) : (
        packets.map((packet) => {
          const task =
            packet.productionTaskId === null
              ? undefined
              : taskById.get(packet.productionTaskId);
          const approval = state.approvalRequests
            .filter((request) => request.taskId === packet.productionTaskId)
            .sort((left, right) =>
              right.createdAt.localeCompare(left.createdAt),
            )[0];
          const evidence =
            approval?.evidenceArtifactIds
              .map((id) => artifactsById.get(id))
              .filter((artifact) => artifact !== undefined) ?? [];
          return (
            <section className="content-packet" key={packet.id}>
              <header>
                <div>
                  <p className="eyebrow">{packet.milestone.label}</p>
                  <h3>{packet.objective}</h3>
                </div>
                <div>
                  <span className={`status status--${packet.status}`}>
                    {label(packet.status)}
                  </span>
                  <div className="mono muted">{shortId(packet.id)}</div>
                </div>
              </header>

              <p className="content-recommendation">
                <b>Recommendation:</b> {packet.recommendation}
              </p>
              <div className="facts">
                <div>
                  <b>Town source</b>
                  <span className="mono">{packet.sourceDigest.slice(0, 12)}</span>
                </div>
                <div>
                  <b>Engagement data</b>
                  {label(packet.engagementDataStatus)}
                </div>
                <div>
                  <b>Created</b>
                  {formatWhen(packet.createdAt)}
                </div>
                <div>
                  <b>Production</b>
                  {task ? label(task.status) : "Not selected"}
                </div>
              </div>
              {packet.dataGaps.length > 0 && (
                <div className="notice">
                  <b>Known data gaps</b>
                  <ul>
                    {packet.dataGaps.map((gap) => (
                      <li key={gap}>{gap}</li>
                    ))}
                  </ul>
                </div>
              )}
              {packet.priorContentNotes.length > 0 && (
                <div className="notice">
                  <b>Previous-content review</b>
                  <ul>
                    {packet.priorContentNotes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}

              {evidence.length > 0 && (
                <>
                  <h4>Private production evidence</h4>
                  <ul className="criteria">
                    {evidence.map((artifact) => {
                      const url = `/api/artifacts/${artifact.id}`;
                      const image =
                        artifact.safeToDisplay &&
                        artifact.mediaType.startsWith("image/");
                      const video =
                        artifact.safeToDisplay &&
                        artifact.mediaType.startsWith("video/");
                      return (
                        <li className="evidence-item" key={artifact.id}>
                          <span>
                            <b>{label(artifact.kind)}</b> - {artifact.label}{" "}
                            <span className="muted">
                              ({artifact.mediaType}, {artifact.sizeBytes} bytes)
                            </span>
                          </span>
                          {artifact.location.kind === "object" && image && (
                            <a href={url} target="_blank" rel="noreferrer">
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                className="evidence-preview"
                                src={url}
                                alt={artifact.label}
                              />
                            </a>
                          )}
                          {artifact.location.kind === "object" && video && (
                            <video
                              className="evidence-preview"
                              controls
                              preload="metadata"
                              src={url}
                            />
                          )}
                          {artifact.location.kind === "object" &&
                            !image &&
                            !video && (
                              <a
                                className="evidence-open"
                                href={url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Open private evidence
                              </a>
                            )}
                          {artifact.location.kind === "git" && (
                            <code className="mono">
                              {`git show ${artifact.location.commitSha}:${artifact.location.repositoryPath}`}
                            </code>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}

              <div className="content-concepts">
                {packet.concepts.map((concept) => (
                  <article className="content-concept" key={concept.id}>
                    <header>
                      <div>
                        <p className="eyebrow">{label(concept.format)}</p>
                        <h4>{concept.title}</h4>
                      </div>
                      <span>{concept.durationSeconds}s</span>
                    </header>
                    <p className="content-hook">{concept.hook}</p>
                    <p>{concept.rationale}</p>
                    <h5>Storyboard</h5>
                    <ol className="storyboard">
                      {concept.storyboard.map((beat) => (
                        <li key={beat.order}>
                          <b>{beat.seconds}</b>
                          <span>{beat.visual}</span>
                          <small>{beat.onScreenText}</small>
                        </li>
                      ))}
                    </ol>
                    <h5>Voiceover</h5>
                    <p>{concept.voiceover}</p>
                    <h5>Caption</h5>
                    <p>{concept.caption}</p>
                    <h5>Pinned comment</h5>
                    <p>{concept.pinnedComment}</p>
                    <p className="mono">{concept.hashtags.join(" ")}</p>
                    <h5>Blender brief</h5>
                    <p>
                      {concept.blenderBrief.camera}.{" "}
                      {concept.blenderBrief.animation}
                    </p>
                    {packet.status === "draft" && (
                      <SelectConceptForm
                        packetId={packet.id}
                        conceptId={concept.id}
                        expectedVersion={packet.version}
                      />
                    )}
                    {packet.selectedConceptId === concept.id && (
                      <p className="notice">Selected by an owner</p>
                    )}
                  </article>
                ))}
              </div>
            </section>
          );
        })
      )}
    </>
  );
}
