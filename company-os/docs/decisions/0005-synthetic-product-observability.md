# ADR 0005: Synthetic Product Health Creates Evidence, Not Authority

Date: 2026-07-29
Status: Accepted
Decision owners: Cade and Zach

## Context

Public HTTP reachability alone cannot reveal whether a visitor can load the
homepage and enter the 3D town. Browser checks can reveal broken assets, client
errors, failed requests, and severe regressions, but they must not capture
visitor content or become an automatic production-write path.

## Decision

Run an hourly, credential-free Playwright journey against the public homepage
and `town.html#walk`. Persist only status codes, bounded timings, request
counts, and error counts. Do not store page bodies, chat, account data,
screenshots, browser storage, or credentials.

Evaluate every immutable snapshot inside Postgres. Create an alert for public
unavailability, browser errors, request failures, homepage DOM readiness above
four seconds, or town readiness above thirty seconds. Alerts are private,
append-only observations. They carry no capability and cannot create a task,
approval, merge, deployment, or production mutation.

An authenticated owner may ask the Chief Executive to create one read-only
diagnostic task for an alert. The normal planner, capability limits, review,
and approval kernel remain authoritative. Remediation is never automatic.

## Consequences

- Product failures remain visible even when the application returns HTTP 200.
- The dashboard shows evidence and a bounded path to diagnosis.
- Hourly retries are idempotent and worker failures back off normally.
- Personal-machine sleep can delay a journey; snapshot freshness says so.
- Deeper signup, claim, retention, and database health still require approved
  read-only production integrations.

## Review Trigger

Revisit when a hosted browser runner replaces the personal-machine worker, or
when approved production telemetry can add authenticated journey and retention
signals without exposing personal data.
