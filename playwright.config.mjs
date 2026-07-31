import { defineConfig, devices } from "@playwright/test";

const externalBaseURL = process.env.FOLLOWVILLE_BASE_URL;

export default defineConfig({
  testDir: "./tests",
  // GitHub's shared software-rendered Chromium can take roughly twice as long
  // as a local GPU for the full Three.js walking/map/chat/pause story.
  timeout: 90_000,
  expect: { timeout: 15_000 },
  // Every story lives in one spec file, so `fullyParallel: false` meant the
  // whole suite ran serially in a single worker no matter how many cores the
  // machine had -- about 33 minutes on CI, and every failure was another 33.
  // Each test gets its own browser context and the server is read-only, so
  // there is no shared state to protect. Measured at 9.1 minutes serial
  // against 6.6 with two workers locally.
  fullyParallel: true,
  // Two, not more: each worker holds a Chromium rendering the town in
  // software on a shared two-core runner, and the memory matters more than
  // the parallelism beyond this.
  workers: 2,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: externalBaseURL || "http://127.0.0.1:8765",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ],
  webServer: externalBaseURL ? undefined : {
    command: "node tests/serve.mjs",
    url: "http://127.0.0.1:8765/index.html",
    reuseExistingServer: !process.env.CI,
    timeout: 15_000
  }
});
