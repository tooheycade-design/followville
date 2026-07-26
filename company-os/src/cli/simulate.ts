import { simulateGoal } from "../orchestration/simulation.js";

const objective =
  process.argv.slice(2).join(" ").trim() ||
  "Add a reviewed project-status summary without changing production.";

const result = simulateGoal({
  title: "Local Company OS demonstration",
  objective,
});

console.log(
  JSON.stringify(
    {
      mode: result.mode,
      goal: result.goal.title,
      taskStatus: result.task.status,
      worker: result.task.assignedAgentId,
      reviewer: result.task.reviewerAgentId,
      approval: {
        action: result.approvalRequest.action,
        status: result.approvalRequest.status,
        requiredApprovals: result.approvalRequest.requiredApprovals,
      },
      auditEventCount: result.auditEvents.length,
      executedSideEffects: result.executedSideEffects.length,
      totalModelCostUsdMicros: result.totalModelCostUsdMicros,
    },
    null,
    2,
  ),
);
