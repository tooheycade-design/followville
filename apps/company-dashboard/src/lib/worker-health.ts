import type { WorkerNode } from "@followville/company-os-core";

export interface WorkerHealth {
  label: "online" | "delayed" | "draining" | "offline" | "error";
  className: "approved" | "pending" | "denied";
}

export function workerHealth(
  worker: Pick<WorkerNode, "status" | "lastSeenAt">,
  now = Date.now(),
): WorkerHealth {
  if (worker.status === "error") {
    return { label: "error", className: "denied" };
  }
  if (worker.status === "offline") {
    return { label: "offline", className: "denied" };
  }
  if (worker.status === "draining") {
    return { label: "draining", className: "pending" };
  }

  const ageMs = now - Date.parse(worker.lastSeenAt);
  if (ageMs <= 90_000) {
    return { label: "online", className: "approved" };
  }
  if (ageMs <= 5 * 60_000) {
    return { label: "delayed", className: "pending" };
  }
  return { label: "offline", className: "denied" };
}
