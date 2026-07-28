import assert from "node:assert/strict";
import test from "node:test";

import { providerEnvironment } from "./environment.js";

test("model providers receive runtime essentials but no control-plane secrets", () => {
  const environment = providerEnvironment({
    PATH: "C:\\tools",
    USERPROFILE: "C:\\Users\\owner",
    APPDATA: "C:\\Users\\owner\\AppData\\Roaming",
    CODEX_HOME: "C:\\Users\\owner\\.codex",
    SUPABASE_SECRET_KEY: "secret-database-key",
    COMPANY_OS_GITHUB_PRIVATE_KEY_BASE64: "private-key",
    OPENAI_API_KEY: "paid-api-key",
    ANTHROPIC_API_KEY: "paid-api-key",
    RANDOM_SECRET: "also-secret",
  });

  assert.equal(environment["PATH"], "C:\\tools");
  assert.equal(environment["USERPROFILE"], "C:\\Users\\owner");
  assert.equal(environment["CODEX_HOME"], "C:\\Users\\owner\\.codex");
  assert.equal(environment["GIT_TERMINAL_PROMPT"], "0");
  assert.equal(environment["SUPABASE_SECRET_KEY"], undefined);
  assert.equal(environment["COMPANY_OS_GITHUB_PRIVATE_KEY_BASE64"], undefined);
  assert.equal(environment["OPENAI_API_KEY"], undefined);
  assert.equal(environment["ANTHROPIC_API_KEY"], undefined);
  assert.equal(environment["RANDOM_SECRET"], undefined);
});
