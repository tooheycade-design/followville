import { mkdir } from "node:fs/promises";
import { chromium } from "@playwright/test";

const output = new URL("../avatar_assets/avatar_v1/look-thumb/", import.meta.url);
await mkdir(output, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1200, height: 760 }, deviceScaleFactor: 1 });
await page.goto("http://127.0.0.1:8765/town.html#walk", { waitUntil: "domcontentloaded" });
await page.locator("#loading").waitFor({ state: "hidden", timeout: 60_000 });
await page.keyboard.press("KeyV");
await page.locator("#avatarStudio").waitFor({ state: "visible" });
await page.addStyleTag({ content: "#avatarStudioBrand,#avatarPreviewHelp,#avatarStudioClose{display:none!important}" });
await page.locator("[data-avatar-tab='look']").click();

const ids = await page.locator("[data-avatar-kind='look']").evaluateAll(buttons =>
  buttons.map(button => button.dataset.avatarId)
);
for (const id of ids) {
  await page.locator(`[data-avatar-kind='look'][data-avatar-id='${id}']`).click();
  await page.waitForFunction(() => !document.querySelector("#avatarPreviewCanvas")?.dataset.loading);
  await page.waitForTimeout(180);
  await page.locator("#avatarPreviewCanvas").screenshot({
    path: new URL(`${id}.jpg`, output).pathname.slice(1),
    type: "jpeg",
    quality: 72,
  });
  console.log(`FOLLOWVILLE_AVATAR_THUMB=${id}`);
}

await browser.close();
