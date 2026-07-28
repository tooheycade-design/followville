import { createReadStream } from "node:fs";
import { mkdir, realpath, stat, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import path from "node:path";

import { chromium } from "@playwright/test";

const [rootArgument, outputArgument] = process.argv.slice(2);
if (!rootArgument || !outputArgument) {
  throw new Error("Usage: browser-preview.mjs <worktree> <relative-output-dir>");
}

const root = path.resolve(rootArgument);
const realRoot = await realpath(root);
const output = path.resolve(root, outputArgument);
const relativeOutput = path.relative(root, output);
if (
  relativeOutput.startsWith("..") ||
  path.isAbsolute(relativeOutput) ||
  relativeOutput.length === 0
) {
  throw new Error("Browser evidence directory must be inside the worktree.");
}
await mkdir(output, { recursive: true });

const mime = {
  ".css": "text/css; charset=utf-8",
  ".glb": "model/gltf-binary",
  ".html": "text/html; charset=utf-8",
  ".jpg": "image/jpeg",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".mp4": "video/mp4",
  ".png": "image/png",
  ".svg": "image/svg+xml",
};

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url || "/", "http://127.0.0.1");
    let pathname = decodeURIComponent(url.pathname);
    if (pathname === "/") pathname = "/index.html";
    if (pathname === "/today" || /^\/house\/\d+\/?$/.test(pathname)) {
      pathname = "/town.html";
    }
    const file = path.resolve(root, pathname.replace(/^\/+/, ""));
    const relative = path.relative(root, file);
    if (relative.startsWith("..") || path.isAbsolute(relative)) {
      response.writeHead(403).end("Forbidden");
      return;
    }
    const resolvedFile = await realpath(file);
    const resolvedRelative = path.relative(realRoot, resolvedFile);
    if (
      resolvedRelative.startsWith("..") ||
      path.isAbsolute(resolvedRelative)
    ) {
      response.writeHead(403).end("Forbidden");
      return;
    }
    const info = await stat(resolvedFile);
    if (!info.isFile()) throw new Error("Not a file");
    response.writeHead(200, {
      "Cache-Control": "no-store",
      "Content-Length": info.size,
      "Content-Type":
        mime[path.extname(file).toLowerCase()] || "application/octet-stream",
    });
    if (request.method === "HEAD") response.end();
    else createReadStream(resolvedFile).pipe(response);
  } catch {
    response.writeHead(404, { "Content-Type": "text/plain" }).end("Not found");
  }
});

await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(0, "127.0.0.1", resolve);
});
const address = server.address();
if (address === null || typeof address === "string") {
  throw new Error("Preview server did not expose a TCP port.");
}
const baseUrl = `http://127.0.0.1:${address.port}`;

const artifacts = [];
const captures = [];
let browser;
try {
  browser = await chromium.launch({ headless: true });

  async function capture({
    name,
    route,
    viewport,
    waitForTown = false,
    fullPage = false,
  }) {
    const context = await browser.newContext({
      viewport,
      deviceScaleFactor: 1,
      reducedMotion: "reduce",
    });
    const traceName = `${name}-trace.zip`;
    const screenshotName = `${name}.png`;
    const errors = [];
    const failedRequests = [];
    const ignoredRequests = [];
    const page = await context.newPage();
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(`console: ${message.text()}`);
    });
    page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
    page.on("response", (response) => {
      if (response.status() >= 400) {
        failedRequests.push(
          `${response.request().method()} ${response.url()} - HTTP ${response.status()}`,
        );
      }
    });
    page.on("requestfailed", (request) => {
      const failure = `${request.method()} ${request.url()} - ${
        request.failure()?.errorText ?? "failed"
      }`;
      const requestUrl = new URL(request.url());
      if (request.failure()?.errorText === "net::ERR_ABORTED") {
        // Reduced-motion video selection and the town's district streaming
        // controller both cancel speculative requests deliberately.
        ignoredRequests.push(failure);
      } else {
        failedRequests.push(failure);
      }
    });
    await context.tracing.start({
      screenshots: true,
      snapshots: true,
      sources: false,
    });
    try {
      const response = await page.goto(`${baseUrl}${route}`, {
        waitUntil: "domcontentloaded",
        timeout: 45_000,
      });
      if (response === null || !response.ok()) {
        throw new Error(`Navigation failed with ${response?.status() ?? "no response"}.`);
      }
      if (waitForTown) {
        await page.locator("#loading").waitFor({ state: "hidden", timeout: 60_000 });
        await page.waitForTimeout(1_000);
      } else {
        await page.locator("body").waitFor({ state: "visible", timeout: 15_000 });
        await page.waitForTimeout(500);
      }
      await page.screenshot({
        path: path.join(output, screenshotName),
        fullPage,
      });
      artifacts.push(
        path.posix.join(outputArgument.replaceAll("\\", "/"), screenshotName),
      );
    } catch (error) {
      errors.push(`capture: ${error.message}`);
    } finally {
      await context.tracing.stop({ path: path.join(output, traceName) });
      artifacts.push(
        path.posix.join(outputArgument.replaceAll("\\", "/"), traceName),
      );
      await context.close();
    }
    captures.push({
      name,
      route,
      viewport,
      errors,
      failedRequests,
      ignoredRequests,
    });
  }

  await capture({
    name: "desktop-home",
    route: "/index.html",
    viewport: { width: 1440, height: 900 },
    fullPage: true,
  });
  await capture({
    name: "desktop-town",
    route: "/town.html#walk",
    viewport: { width: 1440, height: 900 },
    waitForTown: true,
  });
  await capture({
    name: "mobile-home",
    route: "/index.html",
    viewport: { width: 390, height: 844 },
    fullPage: true,
  });
} finally {
  await browser?.close();
  await new Promise((resolve) => server.close(resolve));
}

const passed = captures.every(
  (capture) =>
    capture.errors.length === 0 && capture.failedRequests.length === 0,
);
const reportName = "browser-preview-report.json";
await writeFile(
  path.join(output, reportName),
  JSON.stringify(
    {
      passed,
      generatedAt: new Date().toISOString(),
      captures,
      artifacts,
    },
    null,
    2,
  ),
  "utf8",
);
artifacts.push(path.posix.join(outputArgument.replaceAll("\\", "/"), reportName));

process.stdout.write(JSON.stringify({ passed, artifacts, captures }));
process.exitCode = passed ? 0 : 1;
