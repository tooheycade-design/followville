import { NextResponse } from "next/server";

import { currentOwner } from "@/lib/auth";
import { signedArtifactUrl } from "@/lib/artifact-storage";
import { companyRepository } from "@/lib/state";

export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  context: { params: Promise<{ artifactId: string }> },
) {
  const owner = await currentOwner();
  if (owner === null) {
    return NextResponse.json(
      { error: "Owner authentication required." },
      { status: 401, headers: { "Cache-Control": "private, no-store" } },
    );
  }

  const { artifactId } = await context.params;
  const state = await companyRepository().load();
  const artifact = state.evidenceArtifacts.find(
    (candidate) =>
      candidate.id === artifactId &&
      candidate.organizationId === owner.organizationId &&
      candidate.visibility === "owner_only" &&
      candidate.location.kind === "object",
  );
  if (artifact === undefined) {
    return NextResponse.json(
      { error: "Evidence not found." },
      { status: 404, headers: { "Cache-Control": "private, no-store" } },
    );
  }

  const url = await signedArtifactUrl(artifact);
  if (url === null) {
    return NextResponse.json(
      { error: "Evidence is temporarily unavailable." },
      { status: 503, headers: { "Cache-Control": "private, no-store" } },
    );
  }
  return NextResponse.redirect(url, {
    status: 307,
    headers: {
      "Cache-Control": "private, no-store",
      "Referrer-Policy": "no-referrer",
    },
  });
}
