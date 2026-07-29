# ADR 0006: Blender Candidates Use Trusted Import and Re-Export

Date: 2026-07-29
Status: Accepted
Decision owners: Cade and Zach

## Context

Followville needs Blender workers for both optimized website assets and richer
Instagram cinematics. Blender can also execute Python and load linked data, so
opening arbitrary `.blend` files or agent-authored scripts would give model
output access beyond its task worktree.

## Decision

Accept only `.glb` and `.gltf` candidates inside an isolated task worktree.
Validate every external glTF URI before Blender starts. Launch Blender with a
factory scene and auto-execution disabled, then run only the repository-owned
verification script.

The verifier imports the candidate, records geometry, materials, textures,
missing assets, and animation range, creates front, side, and rear renders,
creates a bounded MP4 when animation exists, and re-exports a validated GLB.
Runtime candidates fail when they exceed
explicit web limits. Candidates under `company-os/candidates/cinematic/` are
reported separately and are not judged against website limits.

Do not execute agent-authored Blender Python or open candidate `.blend` files
until an operating-system sandbox can confine filesystem and process access.
Canonical Followville scenes and world files remain prohibited.

## Consequences

- Owners receive useful visual and technical evidence from real Blender.
- Website and cinematic assets are no longer treated as one pipeline.
- Candidate output remains checkpointed and evidence remains private.
- General procedural Blender creation is still unavailable to autonomous
  agents; they must produce interchange candidates or await a stronger sandbox.

## Review Trigger

Revisit when the worker can run Blender inside a disposable VM or container
with a read-only trusted script mount, a task-only writable volume, no secrets,
and network disabled.
