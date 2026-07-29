-- Adds query support and closes the last mutation path on concept decisions.

begin;

create index content_packets_project_created_idx
  on company_ops.content_packets (project_id, created_at desc);

create trigger content_decisions_reject_truncate
before truncate on company_ops.content_concept_decisions
for each statement execute function company_ops.reject_content_decision_mutation();

commit;
