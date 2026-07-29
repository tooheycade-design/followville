import { chromium } from "@playwright/test";

const endpoint = process.argv[2] || "https://followville-kappa.vercel.app/";
const base = new URL(endpoint);
if (base.protocol !== "https:") {
  throw new Error("Product health endpoint must use HTTPS.");
}

const metrics = {
  homeReachable: false,
  homeStatusCode: 0,
  homeDomContentLoadedMs: 0,
  homeLoadMs: 0,
  townReachable: false,
  townStatusCode: 0,
  townReadyMs: 0,
  clientErrorCount: 0,
  failedRequestCount: 0,
  apiRequestCount: 0,
  apiAverageMs: 0,
  apiFailureCount: 0,
};

const apiDurations = [];
let browser;
try {
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const requestStarts = new Map();

  page.on("console", (message) => {
    if (message.type() === "error") metrics.clientErrorCount += 1;
  });
  page.on("pageerror", () => {
    metrics.clientErrorCount += 1;
  });
  page.on("request", (request) => {
    requestStarts.set(request, Date.now());
  });
  page.on("response", (response) => {
    const request = response.request();
    const started = requestStarts.get(request);
    requestStarts.delete(request);
    if (response.status() >= 400) {
      metrics.failedRequestCount += 1;
    }
    if (
      started !== undefined &&
      /\/(?:rest|auth)\/v1\//.test(response.url())
    ) {
      metrics.apiRequestCount += 1;
      apiDurations.push(Date.now() - started);
      if (response.status() >= 400) metrics.apiFailureCount += 1;
    }
  });
  page.on("requestfailed", (request) => {
    requestStarts.delete(request);
    if (request.failure()?.errorText !== "net::ERR_ABORTED") {
      metrics.failedRequestCount += 1;
    }
  });

  try {
    const homeResponse = await page.goto(new URL("/", base).toString(), {
      waitUntil: "load",
      timeout: 45_000,
    });
    metrics.homeStatusCode = homeResponse?.status() ?? 0;
    metrics.homeReachable = homeResponse?.ok() === true;
    const navigation = await page.evaluate(() => {
      const entry = performance.getEntriesByType("navigation")[0];
      if (!(entry instanceof PerformanceNavigationTiming)) return null;
      return {
        domContentLoaded: Math.round(entry.domContentLoadedEventEnd),
        load: Math.round(entry.loadEventEnd),
      };
    });
    metrics.homeDomContentLoadedMs = navigation?.domContentLoaded ?? 0;
    metrics.homeLoadMs = navigation?.load ?? 0;
  } catch {
    metrics.clientErrorCount += 1;
  }

  const townStarted = Date.now();
  try {
    const townResponse = await page.goto(
      new URL("/town.html#walk", base).toString(),
      { waitUntil: "domcontentloaded", timeout: 45_000 },
    );
    metrics.townStatusCode = townResponse?.status() ?? 0;
    await page.locator("#loading").waitFor({ state: "hidden", timeout: 60_000 });
    metrics.townReachable = townResponse?.ok() === true;
  } catch {
    metrics.clientErrorCount += 1;
  }
  metrics.townReadyMs = Date.now() - townStarted;

  if (apiDurations.length > 0) {
    metrics.apiAverageMs = Math.round(
      apiDurations.reduce((sum, value) => sum + value, 0) /
        apiDurations.length,
    );
  }
  await context.close();
} finally {
  await browser?.close();
}

process.stdout.write(
  JSON.stringify({
    generatedAt: new Date().toISOString(),
    endpoint: base.toString(),
    metrics,
  }),
);
