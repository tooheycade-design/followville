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
  // Serial, and it has to stay that way on CI.
  //
  // Two workers cut the suite from 9.1 minutes to 6.6 on a developer machine,
  // so this was briefly set to run in parallel. On GitHub's two shared cores
  // it took the browser job from one failure to seven: every one a timeout
  // with the locator resolved but never actionable, which is what a starved
  // renderer looks like. Each worker holds a Chromium rendering the town in
  // software, and two of those do not fit. The measurement was real and the
  // machine it was taken on was not the machine that matters.
  //
  // Parallelism here needs either a bigger runner or a lighter page, not a
  // higher worker count.
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
