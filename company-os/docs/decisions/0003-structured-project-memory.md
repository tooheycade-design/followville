# ADR 0003: Structured, Bounded Project Memory

Date: 2026-07-29
Status: Accepted
Decision owners: Cade and Zach

## Context

Followville's operating knowledge spans canonical state, town rules, assets,
website behavior, content history, accepted and retired ideas, incidents, and
owner decisions. Passing all of that text to every model call is expensive,
hard to audit, and gives stale or irrelevant text unnecessary influence.

The existing private `company_ops.memories` table had provenance and lifecycle
fields but no explicit domain category, role audience, correction chain, active
contradiction rule, or bounded retrieval contract.

## Decision

Store project memory as append-only, source-backed records with:

- an explicit category, role audience, tags, source reference, SHA-256 digest,
  confidence, version, expiry, and correction chain;
- one active record per organization, project, category, and case-insensitive
  subject;
- authenticated owner corrections that append a new confirmed version;
- service-only retrieval filtered by role and expiry, ranked by confidence,
  query, and tags, and capped at 25 records;
- a worker prompt cap of eight records for each task.

Seed the initial Followville facts only from canonical `world_state.json` and
`AGENTS.md`. Record absence of an approved monetization model as requiring
owner verification rather than inventing one.

Use PostgreSQL full-text ranking and tags first. Do not add vector embeddings
until corpus size or measured retrieval failures justify another model,
indexing pipeline, cost surface, and injection boundary.

## Consequences

Positive:

- owners can see exactly what the team believes and where it came from;
- corrections preserve history and reject stale browser submissions;
- roles receive compact relevant context instead of the full store;
- contradictory active facts fail at the database boundary;
- no embedding provider, background indexer, or new secret is required.

Negative:

- initial retrieval depends on maintained subjects and tags;
- facts whose subject changes substantially require a deliberate new subject
  or a correction of the existing record;
- repository-derived facts must be refreshed after canonical growth or policy
  changes.

## Review Trigger

Revisit after 500 active records, repeated measured retrieval misses, a need
for cross-language semantic search, or evidence that keyword and tag ranking
cannot keep the eight-record worker context relevant.
