import {
  StructuredMessageSchema,
  digest,
  type StructuredMessage,
} from "@followville/company-os-core";

export interface AgentMessageInput {
  task: {
    id: string;
    organizationId: string;
    projectId: string;
    goalId: string;
  };
  senderId: string;
  recipientId: string;
  type: StructuredMessage["type"];
  priority: StructuredMessage["priority"];
  contextSummary: string;
  requestedAction: string | null;
  expectedOutput: string | null;
  evidenceArtifactIds: readonly string[];
  evidenceIsDurable?: boolean;
  now: Date;
}

export function createAgentMessage(
  input: AgentMessageInput,
  idFactory: () => string,
): StructuredMessage {
  const createdAt = input.now.toISOString();
  const contextSummary = input.contextSummary.slice(0, 8_000);
  const evidenceArtifactIds = input.evidenceIsDurable
    ? [...input.evidenceArtifactIds].slice(0, 25)
    : [];
  const fingerprint = digest({
    taskId: input.task.id,
    senderId: input.senderId,
    recipientId: input.recipientId,
    type: input.type,
    contextSummary,
    requestedAction: input.requestedAction,
    evidenceArtifactIds,
  });
  return StructuredMessageSchema.parse({
    id: idFactory(),
    organizationId: input.task.organizationId,
    projectId: input.task.projectId,
    goalId: input.task.goalId,
    taskId: input.task.id,
    threadId: input.task.id,
    senderType: "agent",
    senderId: input.senderId,
    recipientType: "agent",
    recipientId: input.recipientId,
    type: input.type,
    priority: input.priority,
    requestedAction: input.requestedAction,
    contextSummary,
    evidenceArtifactIds,
    expectedOutput: input.expectedOutput,
    deadlineAt: null,
    confidence: "confirmed",
    estimatedCostUsdMicros: 0,
    relatedFiles: [],
    relatedCommits: [],
    status: "created",
    fingerprint,
    createdAt,
    expiresAt: new Date(
      input.now.getTime() + 7 * 24 * 60 * 60 * 1_000,
    ).toISOString(),
  });
}
