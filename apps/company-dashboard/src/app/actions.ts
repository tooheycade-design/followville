"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { decideApproval, submitGoal } from "@/lib/commands";
import { OWNER_COOKIE, OWNERS, ownerById } from "@/lib/config";

export interface ActionState {
  ok: boolean;
  message: string;
}

export async function submitGoalAction(
  _previous: ActionState | null,
  formData: FormData,
): Promise<ActionState> {
  const result = await submitGoal({
    title: String(formData.get("title") ?? ""),
    objective: String(formData.get("objective") ?? ""),
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

  const cookieStore = await cookies();
  const decider = ownerById(cookieStore.get(OWNER_COOKIE)?.value);

  const result = await decideApproval({
    approvalRequestId: String(formData.get("approvalRequestId") ?? ""),
    decision,
    comment: String(formData.get("comment") ?? ""),
    deciderUserId: decider.id,
    viewedScopeDigest: String(formData.get("scopeDigest") ?? ""),
  });
  revalidatePath("/", "layout");
  return { ok: result.ok, message: result.message };
}

export async function switchOwnerAction(formData: FormData): Promise<void> {
  const requested = String(formData.get("owner") ?? "");
  if (OWNERS.some((owner) => owner.id === requested)) {
    const cookieStore = await cookies();
    cookieStore.set(OWNER_COOKIE, requested, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
    });
  }
  redirect(String(formData.get("returnTo") ?? "/"));
}
