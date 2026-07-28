import { redirect } from "next/navigation";

import { createAuthClient } from "./supabase/server";

export interface AuthenticatedOwner {
  id: string;
  organizationId: string;
  email: string;
  role: "owner";
}

interface MembershipRow {
  userId: string;
  organizationId: string;
  role: string;
}

export async function currentOwner(): Promise<AuthenticatedOwner | null> {
  let client;
  try {
    client = await createAuthClient();
  } catch {
    return null;
  }
  const { data: claimsData, error: claimsError } = await client.auth.getClaims();
  const subject = claimsData?.claims?.sub;
  if (claimsError || typeof subject !== "string") {
    return null;
  }

  const { data, error } = await client.rpc("company_os_my_membership");
  if (error || data === null || typeof data !== "object") {
    return null;
  }
  const membership = data as unknown as MembershipRow;
  if (membership.userId !== subject || membership.role !== "owner") {
    return null;
  }

  return {
    id: subject,
    organizationId: membership.organizationId,
    email:
      typeof claimsData?.claims.email === "string"
        ? claimsData.claims.email
        : "owner",
    role: "owner",
  };
}

export async function requireOwner(): Promise<AuthenticatedOwner> {
  const owner = await currentOwner();
  if (owner === null) {
    redirect("/login");
  }
  return owner;
}
