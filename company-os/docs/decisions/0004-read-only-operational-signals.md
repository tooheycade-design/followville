# ADR 0004: Read-Only Operational Signals First

Date: 2026-07-29
Status: Accepted
Decision owners: Cade and Zach

## Context

The Company OS needs product reality, including follower growth, site health,
registrations, claims, players, errors, requests, payments, and moderation.
Most of those sources require provider approval or credentials that are not
currently available. Treating an unavailable source as a zero would create
false business conclusions.

The first live probe also demonstrated why observations must remain distinct
from memory: the deployed town had advanced to Day 27 while the Company OS
review branch still contained Day 24 files.

## Decision

Create a private registry of operational sources and an append-only snapshot
ledger. Every source declares its access mode, status, setup requirement, safe
non-secret configuration, last check, and last success.

Connect only two credential-free sources initially:

- deployed public `world_state.json`;
- public website health.

Refresh them every 15 minutes from a registered worker. Store only bounded
metrics, evidence URL, raw-source SHA-256, capture time, freshness, confidence,
and idempotency key. Do not retain the website body.

Keep Instagram, analytics, production application data, payments, and
moderation as `setup_required` until an official or owner-approved read-only
connection exists. Operational observations can inform recommendations but
cannot authorize writes, update memory, approve work, or alter production.

## Consequences

Positive:

- agents can distinguish product reality from repository assumptions;
- unavailable integrations are honest and visible;
- observations are attributable, fresh, immutable, and retry-safe;
- future adapters share one storage and dashboard contract;
- no production credential or scraping workaround is introduced.

Negative:

- the first signal set is intentionally small;
- personal-machine sleep pauses external refreshes, though the last observation
  remains visible with an expired freshness state;
- Instagram and deeper product metrics still require provider or owner setup.

## Review Trigger

Revisit when official Instagram access is available, a dedicated read-only
production database role exists, Vercel Analytics export is approved, or signal
volume requires retention aggregation beyond 500 dashboard snapshots.
