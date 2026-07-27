"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  decideApproval,
  decideHeldTask,
  directCeo,
  submitGoal,
} from "@/lib/commands";
import { requireOwner } from "@/lib/auth";
import { safeReturnPath } from "@/lib/auth-policy";
import { ownerRegistryFor } from "@/lib/config";
import { companyRepository } from "@/lib/state";
import {
  companyOsSiteUrl,
  createAuthClient,
} from "@/lib/supabase/server";

export interface ActionState {
  ok: boolean;
  message: string;
}

export async function submitGoalAction(
  _previous: ActionState | null,
  formData: FormData,
): Promise<ActionState> {
  const owner = await requireOwner();

  const result = await submitGoal({
    title: String(formData.get("title") ?? ""),
    objective: String(formData.get("objective") ?? ""),
    createdByUserId: owner.id,
  });
  revalidatePath("/", "layout");
  return { ok: result.ok, message: result.message };
}

export async function decideApprovalAction(
  _previous: ActionState | null,
  formData: FormData,
): Promise<ActionState> {
  const decision = String(formData.get("decision") ?? "");
  if (
    decision !== "approve" &&
    decision !== "reject" &&
    decision !== "request_changes"
  ) {
    return { ok: false, message: "Unknown decision type." };
  }

  const decider = await requireOwner();

  const result = await decideApproval(
    {
      approvalRequestId: String(formData.get("approvalRequestId") ?? ""),
      decision,
      comment: String(formData.get("comment") ?? ""),
      deciderUserId: decider.id,
      viewedScopeDigest: String(formData.get("scopeDigest") ?? ""),
    },
    companyRepository(),
    ownerRegistryFor(decider.id),
  );
  revalidatePath("/", "layout");
  return { ok: result.ok, message: result.message };
}

export async function decideHeldTaskAction(
  _previous: ActionState | null,
  formData: FormData,
): Promise<ActionState> {
  const decision = String(formData.get("decision") ?? "");
  if (decision !== "release" && decision !== "reject") {
    return { ok: false, message: "Unknown decision type." };
  }

  const decider = await requireOwner();

  const result = await decideHeldTask(
    {
      taskId: String(formData.get("taskId") ?? ""),
      decision,
      comment: String(formData.get("comment") ?? ""),
      deciderUserId: decider.id,
      // Only the boxes the owner actually ticked. Absent means not authorized,
      // which is how an owner narrows a grant.
      grantedCapabilities: formData.getAll("capability").map(String),
      expectedVersion: Number(formData.get("expectedVersion") ?? 0),
    },
    companyRepository(),
    ownerRegistryFor(decider.id),
  );
  revalidatePath("/", "layout");
  return { ok: result.ok, message: result.message };
}

export interface CeoActionState {
  ok: boolean;
  message: string;
  escalations: readonly string[];
  clamped: readonly string[];
}

export async function directCeoAction(
  _previous: CeoActionState | null,
  formData: FormData,
): Promise<CeoActionState> {
  const owner = await requireOwner();

  const result = await directCeo({
    title: String(formData.get("title") ?? ""),
    detail: String(formData.get("detail") ?? ""),
    createdByUserId: owner.id,
  });
  revalidatePath("/", "layout");
  return result;
}

export async function loginAction(formData: FormData): Promise<void> {
  const client = await createAuthClient();
  const destination = safeReturnPath(formData.get("next"));
  const { error } = await client.auth.signInWithPassword({
    email: String(formData.get("email") ?? "").trim(),
    password: String(formData.get("password") ?? ""),
  });
  if (error) {
    const params = new URLSearchParams({
      error: "invalid_credentials",
      next: destination,
    });
    redirect(`/login?${params.toString()}`);
  }
  redirect(destination);
}

export async function requestPasswordResetAction(
  formData: FormData,
): Promise<void> {
  const client = await createAuthClient();
  const redirectTo = new URL("/reset-password", companyOsSiteUrl()).toString();
  await client.auth.resetPasswordForEmail(
    String(formData.get("email") ?? "").trim(),
    { redirectTo },
  );

  // The same response is used for known and unknown addresses.
  redirect("/forgot-password?sent=1");
}

export async function logoutAction(): Promise<void> {
  const client = await createAuthClient();
  await client.auth.signOut();
  redirect("/login");
}
