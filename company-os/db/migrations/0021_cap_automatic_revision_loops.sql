-- Bound automatic revisions in the database.
--
-- Both reviewer and owner feedback move through changes_requested -> queued.
-- Once three review cycles have been recorded, that second transition becomes
-- changes_requested -> failed instead. The task remains visible for owner
-- attention and the decision/review that caused it stays in the audit trail,
-- but no worker can lease a fourth automatic attempt.

begin;

create or replace function company_ops.cap_automatic_revision_loop()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if old.status = 'changes_requested'
     and new.status = 'queued'
     and old.review_cycle_count >= 3 then
    new.status := 'failed';
  end if;
  return new;
end;
$$;

drop trigger if exists tasks_cap_automatic_revision_loop on company_ops.tasks;
create trigger tasks_cap_automatic_revision_loop
before update on company_ops.tasks
for each row execute function company_ops.cap_automatic_revision_loop();

commit;
