import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import {
  claudeExecutableCandidates,
  claudeInvocationArgs,
  claudeSubscriptionUsage,
} from "./claude-code.js";

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

test("Claude revisions fork the recorded session", () => {
  assert.deepEqual(
    claudeInvocationArgs({
      prompt: "Address the review.",
      resumeSessionId: "019faa11-1111-7111-8111-111111111111",
    }),
    [
      "-p",
      "Address the review.",
      "--output-format",
      "json",
      "--resume",
      "019faa11-1111-7111-8111-111111111111",
      "--fork-session",
    ],
  );
});

test("subscription usage keeps tokens but never reports API-equivalent cost as spend", () => {
  assert.deepEqual(
    claudeSubscriptionUsage({
      total_cost_usd: 0.250091,
      usage: {
        input_tokens: 120,
        output_tokens: 30,
        cache_read_input_tokens: 80,
      },
    }),
    {
      inputTokens: 120,
      outputTokens: 30,
      cachedInputTokens: 80,
      costUsdMicros: 0,
    },
  );
});
