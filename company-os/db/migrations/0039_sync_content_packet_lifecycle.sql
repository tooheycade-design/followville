-- Keeps a content packet aligned with its private production task.
-- Approval here means the owner accepted the private packet; publishing remains absent.

begin;

create or replace function company_ops.sync_content_packet_from_task()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  packet_status text;
begin
  if new.status is not distinct from old.status then
    return new;
  end if;

  packet_status := case
    when new.status in (
      'proposed', 'queued', 'in_progress', 'awaiting_review', 'changes_requested'
    ) then 'production_in_progress'
    when new.status = 'awaiting_human_approval' then 'ready_for_owner'
    when new.status in ('approved', 'merged') then 'approved'
    when new.status in ('blocked', 'rejected', 'canceled', 'failed') then 'rejected'
    else null
  end;

  if packet_status is not null then
    update company_ops.content_packets
    set status = packet_status,
        version = version + 1,
        updated_at = clock_timestamp()
    where production_task_id = new.id
      and status <> 'published'
      and status is distinct from packet_status;
  end if;

  return new;
end;
$$;

revoke all on function company_ops.sync_content_packet_from_task() from public;

create trigger tasks_sync_content_packet
after update of status on company_ops.tasks
for each row execute function company_ops.sync_content_packet_from_task();

-- Bring packets selected before this migration into line with their current task.
update company_ops.content_packets packet
set status = case
      when task.status in (
        'proposed', 'queued', 'in_progress', 'awaiting_review', 'changes_requested'
      ) then 'production_in_progress'
      when task.status = 'awaiting_human_approval' then 'ready_for_owner'
      when task.status in ('approved', 'merged') then 'approved'
      when task.status in ('blocked', 'rejected', 'canceled', 'failed') then 'rejected'
      else packet.status
    end,
    version = packet.version + 1,
    updated_at = clock_timestamp()
from company_ops.tasks task
where packet.production_task_id = task.id
  and packet.status <> 'published'
  and packet.status is distinct from case
    when task.status in (
      'proposed', 'queued', 'in_progress', 'awaiting_review', 'changes_requested'
    ) then 'production_in_progress'
    when task.status = 'awaiting_human_approval' then 'ready_for_owner'
    when task.status in ('approved', 'merged') then 'approved'
    when task.status in ('blocked', 'rejected', 'canceled', 'failed') then 'rejected'
    else packet.status
  end;

commit;
