# ADR 0007: Visual Review Must Inspect Verified Pixels

Date: 2026-07-29
Status: Accepted
Decision owners: Cade and Zach

## Context

The technical reviewer and Chief Executive could see artifact names and model
reports, but neither inspected the screenshot or render bytes. That could put
functionally correct but visibly weak work in front of an owner.

## Decision

Add a least-privilege Design Director with read and message capabilities only.
When completed work contains safe owner-only PNG artifacts, download at most
six from the private evidence bucket, verify their recorded byte count,
SHA-256 digest, PNG signature, and bounded dimensions, and place them under
generated names in a temporary directory.

The independent judge must inspect those files and return a closed list of
specific findings. Missing infrastructure, provider errors, altered evidence,
malformed responses, and unknown finding codes fail closed. The visual
decision pins the exact artifact IDs in the audit trail. Remove the temporary
directory after the decision.

## Consequences

- Owners see work that has passed technical, visual, and executive review.
- Evidence labels and file content remain untrusted data, never authority.
- Sensitive, public, inline, git-backed, oversized, and non-image artifacts
  cannot enter the visual-review workspace.
- Tasks without visual evidence continue through the existing technical path.
- Cade and Zach remain the final design authority.

## Review Trigger

Revisit when video review, multi-viewport comparison, or a sandboxed remote
vision service can be added without widening evidence access.
