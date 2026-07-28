-- Keep database worker rows inside the strict dashboard/runtime contract.

begin;

alter table company_ops.worker_nodes
  alter column provider set not null;

commit;
