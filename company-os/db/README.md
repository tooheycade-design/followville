# Database Proposal

The SQL in `migrations/` is a review artifact. It has **not** been applied to
local, preview, staging, or production Supabase.

The proposed tables live in the private `company_ops` schema. Browser roles
receive no schema or table privileges. A future server-side control plane would
use a narrowly held service credential and expose purpose-built functions or
API endpoints after a separate security review.

Before applying any migration:

1. Ratify the constitution and owner roles.
2. Review the migration against a disposable Supabase branch.
3. Add integration tests for every server endpoint.
4. Confirm backup and rollback procedures.
5. Obtain explicit approval from Cade or Zach.
