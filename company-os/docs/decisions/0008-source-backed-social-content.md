# ADR 0008: Social Content Is Source-Backed and Owner-Selected

Date: 2026-07-29

## Decision

The Content Studio pins every packet to a confirmed town snapshot and produces
exactly three complete draft concepts. Missing Instagram metrics are displayed
as a data gap and are never estimated.

Concept selection is its own version-pinned, digest-pinned owner decision. It
does not use or imply a publication approval. The selected concept creates one
private production task scoped to `company-os/content` and isolated cinematic
candidates. Existing technical review, pixel review, artifacts, and owner
approval remain the evidence chain.

The current Blender verifier cannot safely render the authoritative town.
Until a guarded render-only adapter exists, the workflow may produce an exact
storyboard and render brief plus isolated preview candidates, but must not call
the final canonical-town Reel rendered.

There is no Instagram credential, publisher adapter, publish button, scheduled
post, or automatic `social_publish` request in this stage.

## Consequences

- Cade and Zach choose creative direction from the same shared dashboard.
- Retries cannot silently change the concept an owner selected.
- A content task cannot mutate the live town or communicate publicly.
- Publishing remains a future high-risk capability with a separate approval.
