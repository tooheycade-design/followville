import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const destination = "C:\\Users\\cadet\\.codex\\integrations\\quaternius-modular-character-outfits-fantasy";
await mkdir(destination, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ acceptDownloads: true });
await page.goto("https://quaternius.itch.io/modular-character-outfits-fantasy/purchase", { waitUntil: "domcontentloaded" });
await page.locator(".direct_download_btn").click();
await page.waitForLoadState("domcontentloaded");
const downloadPromise = page.waitForEvent("download", { timeout: 60_000 });
await page.getByRole("link", { name: "Download", exact: true }).click();
const download = await downloadPromise;
const output = path.join(destination, download.suggestedFilename());
await download.saveAs(output);
console.log(`DOWNLOADED=${output}`);
await browser.close();
