import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import { claudeExecutableCandidates } from "./claude-code.js";

test("Claude discovery prioritizes an explicit executable", () => {
  const candidates = claudeExecutableCandidates(
    {
      CLAUDE_CODE_PATH: "/trusted/claude",
      PATH: "/usr/bin",
    },
    "/home/worker",
  );

  assert.equal(candidates[0], "/trusted/claude");
});

test("Claude discovery includes npm, native, Homebrew, and PATH installs", () => {
  const candidates = claudeExecutableCandidates(
    {
      APPDATA: "C:\\Users\\worker\\AppData\\Roaming",
      PATH: ["C:\\tools", "/custom/bin"].join(path.delimiter),
    },
    "/home/worker",
  );

  assert.ok(
    candidates.includes(
      path.join(
        "C:\\Users\\worker\\AppData\\Roaming",
        "npm",
        "node_modules",
        "@anthropic-ai",
        "claude-code",
        "bin",
        "claude.exe",
      ),
    ),
  );
  assert.ok(candidates.includes(path.join("/home/worker", ".local", "bin", "claude")));
  assert.ok(candidates.includes("/opt/homebrew/bin/claude"));
  assert.ok(candidates.includes(path.join("/custom/bin", "claude")));
});
