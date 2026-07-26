import { OWNER_USER_ID, type OwnerRegistry } from "@followville/company-os-core";

export interface OwnerIdentity {
  id: string;
  name: string;
}

/**
 * Owner identities.
 *
 * When `COMPANY_OS_OWNERS` is set, it supplies the real Supabase Auth user IDs
 * in `name:uuid` pairs separated by commas. Those IDs are real account
 * identifiers, so they live in the environment rather than the repository.
 * Without it, the fixed development placeholders keep the local JSON store
 * usable with no credentials.
 *
 * This is still a picker, not authentication: it establishes which owner the
 * dashboard acts as, and the database independently rejects any decision from
 * an account that is not an active owner. Supabase Auth sign-in replaces the
 * picker in the next phase.
 */
function parseOwners(): readonly OwnerIdentity[] {
  const configured = process.env.COMPANY_OS_OWNERS;
  if (configured === undefined || configured.trim().length === 0) {
    return [
      { id: OWNER_USER_ID, name: "Cade" },
      { id: "30000000-0000-4000-8000-000000000002", name: "Zach" },
    ];
  }

  const owners = configured
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0)
    .map((entry) => {
      const separator = entry.indexOf(":");
      if (separator <= 0) {
        throw new Error(
          `COMPANY_OS_OWNERS entries must look like "Name:uuid"; received "${entry}".`,
        );
      }
      return {
        name: entry.slice(0, separator).trim(),
        id: entry.slice(separator + 1).trim(),
      };
    });

  if (owners.length === 0) {
    throw new Error("COMPANY_OS_OWNERS was set but produced no owners.");
  }
  return owners;
}

export const OWNERS: readonly OwnerIdentity[] = parseOwners();

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
