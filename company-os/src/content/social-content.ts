import { z } from "zod";

import {
  ORGANIZATION_ID,
  PROJECT_ID,
  SEED_AGENTS,
} from "../config/seed-agents.js";
import {
  GoalSchema,
  TaskSchema,
  type Goal,
  type Task,
} from "../domain/schemas.js";

const IdSchema = z.string().uuid();

export const ContentStoryboardBeatSchema = z
  .object({
    order: z.number().int().min(1).max(8),
    seconds: z.string().min(3).max(20),
    visual: z.string().min(1).max(500),
    onScreenText: z.string().max(160),
    voiceover: z.string().max(500),
  })
  .strict();

export const SocialContentConceptSchema = z
  .object({
    id: IdSchema,
    format: z.enum(["milestone_reveal", "town_story", "community_prompt"]),
    title: z.string().min(1).max(120),
    hook: z.string().min(1).max(220),
    objective: z.string().min(1).max(500),
    durationSeconds: z.number().int().min(6).max(30),
    rationale: z.string().min(1).max(800),
    storyboard: z.array(ContentStoryboardBeatSchema).min(3).max(8),
    voiceover: z.string().min(1).max(2000),
    caption: z.string().min(1).max(2200),
    pinnedComment: z.string().min(1).max(500),
    hashtags: z.array(z.string().regex(/^#[A-Za-z0-9_]+$/)).min(3).max(12),
    blenderBrief: z
      .object({
        mode: z.enum(["cinematic"]),
        camera: z.string().min(1).max(200),
        timeOfDay: z.enum(["day", "sunset", "night"]),
        focus: z.string().min(1).max(300),
        animation: z.string().min(1).max(500),
        runtimeAsset: z.literal(false),
      })
      .strict(),
    risks: z.array(z.string().min(1).max(300)).max(8),
  })
  .strict();

export type SocialContentConcept = z.infer<typeof SocialContentConceptSchema>;

export const SocialContentPacketSchema = z
  .object({
    id: IdSchema,
    organizationId: IdSchema,
    projectId: IdSchema,
    createdByUserId: IdSchema,
    createdByAgentId: IdSchema,
    status: z.enum([
      "draft",
      "concept_selected",
      "production_in_progress",
      "ready_for_owner",
      "approved",
      "rejected",
      "published",
    ]),
    objective: z.string().min(1).max(1000),
    recommendation: z.string().min(1).max(1000),
    milestone: z
      .object({
        day: z.number().int().nonnegative(),
        population: z.number().int().nonnegative(),
        buildingCount: z.number().int().nonnegative(),
        seedCounter: z.number().int().nonnegative(),
        label: z.string().min(1).max(200),
      })
      .strict(),
    sourceSnapshotIds: z.array(IdSchema).max(12),
    sourceDigest: z.string().regex(/^[0-9a-f]{64}$/),
    engagementDataStatus: z.enum(["available", "setup_required", "stale"]),
    dataGaps: z.array(z.string().min(1).max(500)).max(12),
    priorContentNotes: z.array(z.string().min(1).max(1000)).max(12),
    concepts: z.array(SocialContentConceptSchema).length(3),
    selectedConceptId: IdSchema.nullable(),
    productionGoalId: IdSchema.nullable(),
    productionTaskId: IdSchema.nullable(),
    publishApprovalRequestId: IdSchema.nullable(),
    version: z.number().int().positive(),
    createdAt: z.string().datetime({ offset: true }),
    updatedAt: z.string().datetime({ offset: true }),
  })
  .strict()
  .superRefine((packet, context) => {
    if (
      packet.selectedConceptId !== null &&
      !packet.concepts.some((concept) => concept.id === packet.selectedConceptId)
    ) {
      context.addIssue({
        code: "custom",
        message: "Selected concept must belong to the packet",
        path: ["selectedConceptId"],
      });
    }
    if (
      packet.status === "draft" &&
      (packet.selectedConceptId !== null ||
        packet.productionGoalId !== null ||
        packet.productionTaskId !== null)
    ) {
      context.addIssue({
        code: "custom",
        message: "Draft packets cannot cite production work",
        path: ["status"],
      });
    }
  });

export type SocialContentPacket = z.infer<typeof SocialContentPacketSchema>;

export interface SocialContentPlanningInput {
  createdByUserId: string;
  objective?: string;
  milestone: {
    day: number;
    population: number;
    buildingCount: number;
    seedCounter: number;
  };
  sourceSnapshotIds: readonly string[];
  sourceDigest: string;
  engagementDataStatus: "available" | "setup_required" | "stale";
  priorContentNotes: readonly string[];
  idFactory: () => string;
  now?: string;
}

function beats(
  population: number,
  day: number,
  kind: SocialContentConcept["format"],
): SocialContentConcept["storyboard"] {
  if (kind === "milestone_reveal") {
    return [
      { order: 1, seconds: "0-2s", visual: "Open at street level with one current home filling the frame.", onScreenText: "Every follow built this.", voiceover: "Every follow became part of a real town." },
      { order: 2, seconds: "2-5s", visual: "Fast, smooth pullback reveals connected streets and neighborhoods.", onScreenText: `Day ${day}`, voiceover: "Day by day, the streets kept growing." },
      { order: 3, seconds: "5-9s", visual: "Rise into a complete overhead that keeps the whole current town in frame.", onScreenText: `${population.toLocaleString()} residents`, voiceover: `Now ${population.toLocaleString()} people live in Followville.` },
      { order: 4, seconds: "9-12s", visual: "Settle over downtown with a clean hold for the call to action.", onScreenText: "Your house is waiting.", voiceover: "Follow, join the town, and find your place." },
    ];
  }
  if (kind === "town_story") {
    return [
      { order: 1, seconds: "0-2s", visual: "Match-cut from the original founder block to the same present-day angle.", onScreenText: "It started with 10.", voiceover: "Followville started with ten founder homes." },
      { order: 2, seconds: "2-6s", visual: "Three quick geographic match cuts through major growth eras.", onScreenText: "One follower. One home.", voiceover: "Then every new follower added another home." },
      { order: 3, seconds: "6-10s", visual: "Wide orbit showing suburbs, downtown, and feature districts together.", onScreenText: `${population.toLocaleString()} residents later`, voiceover: `Today, ${population.toLocaleString()} residents share one growing town.` },
      { order: 4, seconds: "10-12s", visual: "End on a current unclaimed home and visible front door.", onScreenText: "Come live here.", voiceover: "The next chapter could be yours." },
    ];
  }
  return [
    { order: 1, seconds: "0-3s", visual: "Fly toward open land at the town edge without showing unreleased construction.", onScreenText: "What should we build next?", voiceover: "Followville has reached its next chapter." },
    { order: 2, seconds: "3-7s", visual: "Show three neutral marked zones using edit-only labels, not permanent geometry.", onScreenText: "Park / Shops / Landmark", voiceover: "Should the next shared place be a park, new shops, or a landmark?" },
    { order: 3, seconds: "7-10s", visual: "Return to a populated street with residents and homes visible.", onScreenText: "The town decides.", voiceover: "This town belongs to the people joining it." },
    { order: 4, seconds: "10-12s", visual: "Hold a clean overhead with comment prompt.", onScreenText: "Vote below.", voiceover: "Vote in the comments. We will bring the winner back for owner approval." },
  ];
}

function concept(
  idFactory: () => string,
  kind: SocialContentConcept["format"],
  day: number,
  population: number,
): SocialContentConcept {
  const common = {
    id: idFactory(),
    format: kind,
    durationSeconds: 12,
    storyboard: beats(population, day, kind),
    hashtags: ["#Followville", "#VirtualWorld", "#CommunityBuilt", "#Blender3D"],
    blenderBrief: {
      mode: "cinematic" as const,
      camera:
        kind === "milestone_reveal"
          ? "Street-level opening into a whole-town overhead pullback"
          : kind === "town_story"
            ? "Matched founder/current angles followed by a restrained wide orbit"
            : "Edge-of-town approach, three labeled zones, then whole-town hold",
      timeOfDay: kind === "town_story" ? ("sunset" as const) : ("day" as const),
      focus:
        kind === "community_prompt"
          ? "Current town plus genuinely open land; never depict an owner-unapproved permanent design"
          : "Current canonical town and its real milestone",
      animation:
        "Twelve-second vertical-safe camera move. No automatic world growth, no state mutation, and no permanent scene additions.",
      runtimeAsset: false as const,
    },
  };
  if (kind === "milestone_reveal") {
    return SocialContentConceptSchema.parse({
      ...common,
      title: `${population.toLocaleString()} Residents, One Living Town`,
      hook: "Every follow built this.",
      objective: "Turn the current population milestone into a clear invitation to join.",
      rationale: "The strongest current fact is the scale of the town. A street-to-overhead reveal makes that scale understandable before asking viewers to join.",
      voiceover: `Every follow became part of a real town. Day by day, the streets kept growing. Now ${population.toLocaleString()} people live in Followville. Follow, join the town, and find your place.`,
      caption: `Followville is now home to ${population.toLocaleString()} residents. Every follower adds to the story, and every claimed home makes the town feel more alive. Follow to join, then visit the town and find your place.`,
      pinnedComment: "Would you live downtown, near the park, or on a quiet street?",
      risks: ["The whole-town overhead must keep the newest districts in frame.", "Avoid population claims not supported by the current snapshot."],
    });
  }
  if (kind === "town_story") {
    return SocialContentConceptSchema.parse({
      ...common,
      title: "From Ten Founder Homes to Followville",
      hook: "It started with ten.",
      objective: "Give new viewers an emotional before-and-after story with a simple premise.",
      rationale: "A concise origin story distinguishes Followville from generic procedural city content and explains why every house matters.",
      voiceover: `Followville started with ten founder homes. Then every new follower added another home. Today, ${population.toLocaleString()} residents share one growing town. The next chapter could be yours.`,
      caption: `It started with ten founder homes. On Day ${day}, Followville has grown into a connected town of ${population.toLocaleString()} residents. The rule is still simple: every new follower becomes part of the neighborhood.`,
      pinnedComment: "How long have you been following the town?",
      risks: ["Historical comparison must use verified prior imagery.", "Match cuts should not imply that current buildings existed in older scenes."],
    });
  }
  return SocialContentConceptSchema.parse({
    ...common,
    title: "The Town Chooses What Comes Next",
    hook: "What should Followville build next?",
    objective: "Invite useful participation without promising an unapproved feature.",
    rationale: "A bounded community vote can increase comments and make residents feel involved while keeping Cade and Zach in final control of town design.",
    voiceover: "Followville has reached its next chapter. Should the next shared place be a park, new shops, or a landmark? This town belongs to the people joining it. Vote below. We will bring the winner back for owner approval.",
    caption: "The town is growing, and we want to hear where the community would take it next. Vote below: a public park, a small shopping street, or a new landmark. This is an idea vote, not a construction promise. Cade and Zach make the final call.",
    pinnedComment: "Vote with one word: PARK, SHOPS, or LANDMARK.",
    risks: ["State clearly that voting does not authorize construction.", "Do not show permanent geometry that owners have not approved."],
  });
}

export function buildSocialContentPacket(
  input: SocialContentPlanningInput,
): SocialContentPacket {
  const population = input.milestone.population;
  const day = input.milestone.day;
  return SocialContentPacketSchema.parse({
    id: input.idFactory(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    createdByUserId: input.createdByUserId,
    createdByAgentId: SEED_AGENTS.contentStrategist.id,
    status: "draft",
    objective:
      input.objective?.trim() ||
      `Use the Day ${day} milestone to make viewers understand that Followville is a living community they can join.`,
    recommendation:
      `Lead with the milestone reveal. It uses the strongest confirmed signal ` +
      `(${population.toLocaleString()} residents) and has the clearest conversion path from viewer to resident.`,
    milestone: {
      ...input.milestone,
      label: `Day ${day} / ${population.toLocaleString()} residents / ${input.milestone.buildingCount.toLocaleString()} buildings`,
    },
    sourceSnapshotIds: [...input.sourceSnapshotIds],
    sourceDigest: input.sourceDigest,
    engagementDataStatus: input.engagementDataStatus,
    dataGaps:
      input.engagementDataStatus === "available"
        ? []
        : input.engagementDataStatus === "stale"
          ? [
              "Instagram engagement is connected, but no fresh confirmed snapshot is available.",
              "Concept ranking uses confirmed town state and content history, not stale or invented engagement metrics.",
            ]
          : [
              "Instagram reach, retention, saves, shares, and comment performance are not connected.",
              "Concept ranking uses confirmed town state and content history, not invented engagement metrics.",
            ],
    priorContentNotes: [...input.priorContentNotes].slice(0, 12),
    concepts: [
      concept(input.idFactory, "milestone_reveal", day, population),
      concept(input.idFactory, "town_story", day, population),
      concept(input.idFactory, "community_prompt", day, population),
    ],
    selectedConceptId: null,
    productionGoalId: null,
    productionTaskId: null,
    publishApprovalRequestId: null,
    version: 1,
    createdAt: input.now ?? new Date().toISOString(),
    updatedAt: input.now ?? new Date().toISOString(),
  });
}

export function selectedConcept(
  packet: SocialContentPacket,
  conceptId: string,
): SocialContentConcept {
  const selected = packet.concepts.find((concept) => concept.id === conceptId);
  if (selected === undefined) {
    throw new Error("The selected concept does not belong to this packet.");
  }
  return selected;
}

function productionBrief(
  packet: SocialContentPacket,
  selected: SocialContentConcept,
): string {
  const storyboard = selected.storyboard
    .map(
      (beat) =>
        `${beat.seconds}: ${beat.visual} Text: "${beat.onScreenText}" VO: "${beat.voiceover}"`,
    )
    .join("\n");
  return [
    `Content packet ${packet.id}`,
    `Concept: ${selected.title}`,
    `Hook: ${selected.hook}`,
    `Objective: ${selected.objective}`,
    `Milestone: ${packet.milestone.label}`,
    "",
    "Storyboard:",
    storyboard,
    "",
    `Voiceover: ${selected.voiceover}`,
    `Caption: ${selected.caption}`,
    `Pinned comment: ${selected.pinnedComment}`,
    `Metadata: ${selected.hashtags.join(" ")}`,
    "",
    `Blender camera: ${selected.blenderBrief.camera}`,
    `Blender focus: ${selected.blenderBrief.focus}`,
    `Animation: ${selected.blenderBrief.animation}`,
    "",
    "Create only a cinematic candidate and private preview evidence. Do not",
    "edit world_state.json, town.glb, neighborhood.blend, publish content, or",
    "claim that a concept has been approved by Cade or Zach.",
  ].join("\n");
}

export function buildContentProductionInitiative(input: {
  packet: SocialContentPacket;
  conceptId: string;
  ownerUserId: string;
  goalId: string;
  taskId: string;
  criterionIds: readonly [string, string, string, string];
  now?: string;
}): { goal: Goal; task: Task } {
  const selected = selectedConcept(input.packet, input.conceptId);
  const now = input.now ?? new Date().toISOString();
  const goal = GoalSchema.parse({
    id: input.goalId,
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    createdByUserId: input.ownerUserId,
    title: `Prepare Reel: ${selected.title}`,
    objective: productionBrief(input.packet, selected),
    successDefinition:
      "A private cinematic preview and complete, reviewed social-content packet are ready for an owner decision.",
    constraints: [
      "Drafting and private previews only.",
      "No social publishing or public communication.",
      "No canonical town state or scene mutation.",
      "Cade and Zach retain final creative authority.",
    ],
    riskLevel: "medium",
    budgetUsdMicros: 0,
    status: "active",
    createdAt: now,
  });
  const task = TaskSchema.parse({
    id: input.taskId,
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: goal.id,
    parentTaskId: null,
    title: `Produce private preview: ${selected.title}`,
    objective: productionBrief(input.packet, selected),
    reason:
      "An owner selected this concept from a source-backed Content Studio packet.",
    status: "queued",
    priority: 70,
    riskLevel: "medium",
    assignedAgentId: SEED_AGENTS.engineer.id,
    reviewerAgentId: SEED_AGENTS.reviewer.id,
    dependencyIds: [],
    acceptanceCriteria: [
      {
        id: input.criterionIds[0],
        description: "The storyboard, voiceover, caption, pinned comment, and metadata are preserved in a reviewable packet.",
        verificationMethod: "Inspect the checkpointed packet against the selected concept.",
        required: true,
      },
      {
        id: input.criterionIds[1],
        description: "A cinematic candidate produces private Blender preview renders.",
        verificationMethod: "Run the trusted cinematic Blender candidate verifier.",
        required: true,
      },
      {
        id: input.criterionIds[2],
        description: "Independent technical and pixel-backed visual review pass.",
        verificationMethod: "Inspect recorded reviewer and Design Director audit events.",
        required: true,
      },
      {
        id: input.criterionIds[3],
        description: "No public post, production change, or canonical town mutation occurs.",
        verificationMethod: "Inspect capability grant, changed paths, and audit history.",
        required: true,
      },
    ],
    allowedCapabilities: [
      "repository_read",
      "repository_write",
      "git_checkpoint",
      "test_execute",
      "blender_preview",
      "message_send",
    ],
    repositoryScopes: [
      {
        repository: "followville_repo",
        allowedPathPrefixes: [
          "company-os/content",
          "company-os/candidates/cinematic",
        ],
        deniedPathPrefixes: [
          "world_state.json",
          "town.glb",
          "town_chunks",
          "neighborhood.blend",
        ],
        environments: ["local", "preview"],
      },
    ],
    budgetUsdMicros: 0,
    estimatedCostUsdMicros: 0,
    actualCostUsdMicros: 0,
    retryCount: 0,
    reviewCycleCount: 0,
    branchName: null,
    expectedOutputs: [
      "Complete social-content packet",
      "Cinematic GLB or glTF candidate",
      "Private Blender preview renders",
    ],
    testRequirements: ["Cinematic candidate Blender preview"],
    approvalRequired: true,
    version: 1,
    createdAt: now,
    updatedAt: now,
  });
  return { goal, task };
}
