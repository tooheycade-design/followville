import { defineConfig, devices } from "@playwright/test";

const externalBaseURL = process.env.FOLLOWVILLE_BASE_URL;
const localPort = Number(process.env.FOLLOWVILLE_TEST_PORT || 8765);
const localBaseURL = `http://127.0.0.1:${localPort}`;

export default defineConfig({
  testDir: "./tests",
  // GitHub's shared software-rendered Chromium can take roughly twice as long
  // as a local GPU for the full Three.js walking/map/chat/pause story.
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: externalBaseURL || localBaseURL,
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
    url: `${localBaseURL}/index.html`,
    reuseExistingServer: !process.env.CI,
    timeout: 15_000
  }
});
