# ADR 0002: Postgres Owns Lightweight Hosted Control

Date: 2026-07-28
Status: Accepted
Decision owners: Cade and Zach

## Context

Basic Company OS coordination must continue while both owner machines sleep.
Heavy work still needs local model CLIs, Git worktrees, browsers, and Blender.
The hosted layer therefore needs durable timers and database-local
coordination, not another execution authority.

The current Vercel tier allows daily cron but does not provide dependable
five-minute scheduling. Adding Inngest, Trigger.dev, or Temporal now would add
another credential set, event store, retry model, and operating surface while
the authoritative state machine already lives in Postgres.

## Decision

Use Supabase Cron (`pg_cron`) for lightweight, idempotent control ticks:

- reclaim expired worker leases;
- expire bounded messages;
- measure worker and queue health;
- detect queued tasks with no compatible fresh worker;
- create in-dashboard owner reminders;
- retain daily operating snapshots.

Use Vercel for the authenticated owner UI. Keep model execution, repository
work, browser capture, and Blender capture on registered workers.

The hosted function has no model, repository, GitHub, production, payment,
public communication, or canonical-world capability. Messages and reminders
remain context; they cannot approve or move work.

## Consequences

Positive:

- control continues without an owner computer;
- ticks and results are durable beside the authoritative queue;
- advisory locks and time-bucket uniqueness make retries idempotent;
- no new paid workflow vendor or secret-bearing service is introduced;
- owners can inspect cron history and control snapshots in one database.

Negative:

- complex multi-day workflows still belong in the explicit task state machine;
- database jobs must stay short and SQL-oriented;
- model work waits until a compatible registered machine is online.

## Alternatives

- Vercel Cron: retained for future daily HTTP work; current tier is too coarse
  for lease health.
- Inngest or Trigger.dev: revisit when event fan-out, durable external waits,
  or workflow-level tracing exceeds the database state machine.
- Temporal: deferred until scale and workflow duration justify its operational
  cost.
- Always-on owner machine: rejected as an availability requirement.

## Review Trigger

Revisit after ten concurrent workers, external notification providers, more
than eight concurrent scheduled database jobs, or workflows whose waits and
retries can no longer be expressed clearly as task state.
