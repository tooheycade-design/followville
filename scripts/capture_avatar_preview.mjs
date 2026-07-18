import { chromium } from "@playwright/test";

const browser = await chromium.launch({ headless: true });
const viewportWidth = Number(process.env.CAPTURE_WIDTH || 1440);
const viewportHeight = Number(process.env.CAPTURE_HEIGHT || 900);
const page = await browser.newPage({
  viewport: { width: viewportWidth, height: viewportHeight },
  deviceScaleFactor: 1,
});
const requestedHair = process.argv[2] || "none";
const requestedOutfit = process.argv[3] || "tailored";
const requestedHat = process.argv[4] || "none";
const requestedHeight = process.argv[5] || "adult";
const requestedFace = process.argv[6] || "classic";
const requestedSkin = process.argv[7] || "peach";
const requestedLook = process.argv[8] || "custom";
const requestedTab = process.argv[9] || "body";
await page.addInitScript(({ hair, outfit, hat, height, face, skin, look }) => {
  localStorage.setItem("followville_avatar_v1", JSON.stringify({
    version: 1,
    skin,
    height,
    face,
    hair,
    outfit,
    hat,
    look,
  }));
}, {
  hair: requestedHair,
  outfit: requestedOutfit,
  hat: requestedHat,
  height: requestedHeight,
  face: requestedFace,
  skin: requestedSkin,
  look: requestedLook,
});
const errors = [];
page.on("console", (message) => {
  if (message.type() === "error") errors.push(`console:${message.text()}`);
});
page.on("pageerror", (error) => errors.push(`page:${error.message}`));

await page.goto("http://127.0.0.1:8765/town.html#walk", {
  waitUntil: "domcontentloaded",
});
await page.locator("#loading").waitFor({ state: "hidden", timeout: 60_000 });
await page.keyboard.press("KeyV");
await page.locator("#avatarStudio").waitFor({ state: "visible", timeout: 30_000 });
if (requestedTab !== "body") {
  await page.locator(`[data-avatar-tab='${requestedTab}']`).click();
}
await page.waitForTimeout(3_000);
console.log("CANVAS", await page.locator("#avatarPreviewCanvas").evaluate((canvas) => ({
  width: canvas.width,
  height: canvas.height,
  loading: canvas.dataset.loading || null,
  error: canvas.dataset.error || null,
})));
console.log("BODY", await page.locator("body").getAttribute("data-avatar"));
console.log("ERRORS", errors);
await page.screenshot({
  path: `test-results/avatar-realistic-${requestedTab}-${requestedLook}-${requestedHair}-${requestedOutfit}-${requestedHat}-${requestedHeight}-${requestedFace}-${requestedSkin}.png`,
  fullPage: true,
});
await browser.close();
