import { test, expect } from "@playwright/test";

test("licensed asset review shelf loads and filters the Kenney catalog", async ({ page }) => {
  await page.goto("/asset-library.html");
  await expect(page.locator("body")).toHaveAttribute("data-asset-library-ready", "true");
  await page.locator("#source").selectOption("kenney-furniture-kit");
  await expect(page.locator("body")).toHaveAttribute("data-asset-library-visible", "140");
  await expect(page.locator("[data-source='kenney-furniture-kit']")).toHaveCount(140);

  await page.locator("#search").fill("television modern");
  await expect(page.locator("[data-asset='television_modern']")).toBeVisible();
  await expect(page.locator("[data-source='kenney-furniture-kit']")).toHaveCount(1);
  const image = page.locator("[data-asset='television_modern'] img");
  await expect(image).toHaveJSProperty("complete", true);
  await expect.poll(() => image.evaluate(node => node.naturalWidth)).toBeGreaterThan(0);
});
