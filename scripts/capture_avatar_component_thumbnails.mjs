import { mkdir } from "node:fs/promises";
import { chromium } from "@playwright/test";

const outputRoot = new URL("../avatar_assets/avatar_v1/component-thumb/", import.meta.url);
for (const kind of ["face", "hair", "outfit", "hat"]) {
  await mkdir(new URL(`${kind}/`, outputRoot), { recursive: true });
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1200, height: 760 }, deviceScaleFactor: 1 });
await page.goto("http://127.0.0.1:8765/town.html#walk", { waitUntil: "domcontentloaded" });
await page.locator("#loading").waitFor({ state: "hidden", timeout: 60_000 });
await page.keyboard.press("KeyV");
await page.locator("#avatarStudio").waitFor({ state: "visible" });
await page.addStyleTag({ content: "#avatarStudioBrand,#avatarPreviewHelp,#avatarStudioClose{display:none!important}" });

for (const kind of ["face", "hair", "outfit", "hat"]) {
  await page.locator(`[data-avatar-tab='${kind}']`).click();
  const ids = await page.locator(`[data-avatar-kind='${kind}']`).evaluateAll(buttons =>
    buttons.map(button => button.dataset.avatarId)
  );
  for (const id of ids) {
    await page.locator(`[data-avatar-kind='${kind}'][data-avatar-id='${id}']`).click();
    await page.waitForFunction(() => !document.querySelector("#avatarPreviewCanvas")?.dataset.loading);
    await page.waitForTimeout(160);
    const canvas = page.locator("#avatarPreviewCanvas");
    const destination = new URL(`${kind}/${id}.jpg`, outputRoot).pathname.slice(1);
    if (kind === "outfit") {
      await canvas.screenshot({ path: destination, type: "jpeg", quality: 72 });
    } else {
      const box = await canvas.boundingBox();
      await page.screenshot({
        path: destination,
        type: "jpeg",
        quality: 76,
        clip: {
          x: box.x + box.width * .20,
          y: box.y,
          width: box.width * .60,
          height: box.height * .48,
        },
      });
    }
    console.log(`FOLLOWVILLE_AVATAR_COMPONENT_THUMB=${kind}:${id}`);
  }
}

await browser.close();
