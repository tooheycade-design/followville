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
 * This registry remains the deterministic kernel's local policy input. Web
 * identity comes from a validated Supabase Auth session and database
 * membership; it never comes from this list or from a selectable cookie.
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

export function ownerRegistryFor(userId: string): OwnerRegistry {
  return {
    ...OWNER_REGISTRY,
    ownerUserIds: [...new Set([...OWNER_REGISTRY.ownerUserIds, userId])],
  };
}

export function ownerName(id: string): string {
  return OWNERS.find((owner) => owner.id === id)?.name ?? "Unknown";
}
