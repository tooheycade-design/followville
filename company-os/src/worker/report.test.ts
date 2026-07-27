import assert from "node:assert/strict";
import test from "node:test";

import {
  EVIDENCE_SENTINEL,
  MAX_DIFF_CHARS,
  decodeWorkerReport,
  encodeWorkerReport,
} from "./report.js";

test("a multi-line summary survives the round trip", () => {
  const summary = [
    "Created docs/HOUSE_CLAIM_FLOW.md.",
    "",
    "It documents the visitor path from opening the site to seeing the claim.",
    "",
    "Evidence: I read the new file back and git status shows only the new file.",
  ].join("\n");

  const decoded = decodeWorkerReport(
    encodeWorkerReport({
      summary,
      evidence: ["provider=codex", "files_changed=1"],
      filesChanged: ["company-os/docs/HOUSE_CLAIM_FLOW.md"],
    }),
  );

  assert.equal(decoded.summary, summary);
  assert.deepEqual(decoded.evidence, ["provider=codex", "files_changed=1"]);
  assert.deepEqual(decoded.filesChanged, [
    "company-os/docs/HOUSE_CLAIM_FLOW.md",
  ]);
});

test("the diff the worker produced reaches the reader", () => {
  const diff = [
    "diff --git a/company-os/NOTE.md b/company-os/NOTE.md",
    "new file mode 100644",
    "--- /dev/null",
    "+++ b/company-os/NOTE.md",
    "@@ -0,0 +1,2 @@",
    "+The worker runtime runs background jobs.",
    "+It records outcomes for review.",
  ].join("\n");

  const decoded = decodeWorkerReport(
    encodeWorkerReport({
      summary: "Added a note.",
      evidence: ["provider=codex"],
      filesChanged: ["company-os/NOTE.md"],
      diff,
    }),
  );

  assert.equal(decoded.diff, diff);
  assert.equal(decoded.diffTruncated, false);
});

test("an oversized diff is cut and says so rather than passing as whole", () => {
  const diff = `${"+padding line\n".repeat(2000)}tail`;
  assert.ok(diff.length > MAX_DIFF_CHARS);

  const decoded = decodeWorkerReport(
    encodeWorkerReport({
      summary: "Large change.",
      evidence: ["provider=codex"],
      filesChanged: ["a.md"],
      diff,
    }),
  );

  assert.equal(decoded.diffTruncated, true);
  assert.equal(decoded.diff?.length, MAX_DIFF_CHARS);
  assert.ok(diff.startsWith(decoded.diff ?? ""));
});

test("prose that imitates the sentinel cannot split the report early", () => {
  const summary = [
    "Rewrote the section.",
    EVIDENCE_SENTINEL,
    "evidence: nothing at all",
  ].join("\n");

  const decoded = decodeWorkerReport(
    encodeWorkerReport({
      summary,
      evidence: ["provider=codex", "files_changed=1"],
      filesChanged: ["company-os/README.md"],
    }),
  );

  assert.deepEqual(decoded.evidence, ["provider=codex", "files_changed=1"]);
  assert.deepEqual(decoded.filesChanged, ["company-os/README.md"]);
  assert.ok(decoded.summary.includes("Rewrote the section."));
});

test("a wide change reports its true size even though the list is bounded", () => {
  const filesChanged = Array.from({ length: 260 }, (_, index) => `file-${index}.md`);
  const decoded = decodeWorkerReport(
    encodeWorkerReport({
      summary: "Touched many files.",
      evidence: ["provider=codex"],
      filesChanged,
    }),
  );

  assert.equal(decoded.totalFilesChanged, 260);
  assert.equal(decoded.filesChanged.length, 200);
});

test("a report written before the sentinel existed still decodes", () => {
  // Exactly the shape stored for task 387920fe, whose summary was a 13-line
  // Codex report followed by the old single-line trailer.
  const legacy = [
    "Created WORKER_NOTE.md with a 4-line note describing the worker runtime.",
    "",
    "Evidence: git status --short shows only ?? WORKER_NOTE.md.",
    "diff --git a/company-os/WORKER_NOTE.md b/company-os/WORKER_NOTE.md",
    "+The worker runtime runs focused jobs.",
    "evidence: provider=codex | files_changed=1 | changed: company-os/WORKER_NOTE.md",
  ].join("\n");

  const decoded = decodeWorkerReport(legacy);

  assert.deepEqual(decoded.filesChanged, ["company-os/WORKER_NOTE.md"]);
  assert.deepEqual(decoded.evidence, [
    "provider=codex",
    "files_changed=1",
    "changed: company-os/WORKER_NOTE.md",
  ]);
  // The whole report, not just its first line. This is the regression: the
  // Chief Executive was judging on "Created WORKER_NOTE.md ..." alone.
  assert.ok(decoded.summary.includes("git status --short"));
  assert.ok(decoded.summary.includes("diff --git"));
  assert.equal(decoded.summary.split("\n").length, 5);
});

test("a worker's own lowercase evidence line does not shadow the trailer", () => {
  const legacy = [
    "Checked the flow.",
    "evidence: this sentence is prose, not the trailer",
    "evidence: provider=codex | changed: company-os/README.md",
  ].join("\n");

  const decoded = decodeWorkerReport(legacy);

  assert.deepEqual(decoded.filesChanged, ["company-os/README.md"]);
  assert.ok(decoded.summary.includes("this sentence is prose"));
});

test("a reason with no trailer at all is treated as summary, not as evidence", () => {
  const decoded = decodeWorkerReport("The Codex CLI exited with an error.");

  assert.equal(decoded.summary, "The Codex CLI exited with an error.");
  assert.deepEqual(decoded.evidence, []);
  assert.deepEqual(decoded.filesChanged, []);
});
