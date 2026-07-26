import { OWNER_USER_ID, type OwnerRegistry } from "@followville/company-os-core";

export interface OwnerIdentity {
  id: string;
  name: string;
}

// Local development identities. Phase 1 runs on a local machine without the
// separate development Supabase project, so the dashboard uses an explicit
// owner picker instead of real authentication. Supabase Auth replaces this
// once the development project exists (requires human setup).
export const OWNERS: readonly OwnerIdentity[] = [
  { id: OWNER_USER_ID, name: "Cade" },
  { id: "30000000-0000-4000-8000-000000000002", name: "Zach" },
];

export const OWNER_REGISTRY: OwnerRegistry = {
  ownerUserIds: OWNERS.map((owner) => owner.id),
  operatorUserIds: [],
};

export const OWNER_COOKIE = "fv_dev_owner";

export function ownerById(id: string | undefined): OwnerIdentity {
  const fallback = OWNERS[0];
  if (fallback === undefined) {
    throw new Error("At least one owner identity must be configured.");
  }
  return OWNERS.find((owner) => owner.id === id) ?? fallback;
}

export function ownerName(id: string): string {
  return OWNERS.find((owner) => owner.id === id)?.name ?? "Unknown";
}
