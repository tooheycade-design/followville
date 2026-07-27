-- Separates a recoverable local commit from a publication step.
--
-- `git_commit` was covering both the runtime recording finished work on a
-- task's own review branch and an agent choosing to commit for itself. Those
-- carry different risk: the first cannot leave the machine, the second is a
-- step toward publication. Gating them under one name made the policy read as
-- a contradiction, and made a safe retention action look like a bypass.
--
-- `git_checkpoint` is the local, non-publishing one. `git_commit`,
-- `git_push_review_branch`, `pull_request_create`, `production_merge`, and
-- `production_deploy` are unchanged and still gated as before.
--
-- Adding an enum value is additive and does not alter existing rows.

begin;

alter type company_ops.capability add value if not exists 'git_checkpoint'
  after 'git_branch_create';

commit;
