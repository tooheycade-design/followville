import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

const worldState = JSON.parse(readFileSync(new URL("../world_state.json", import.meta.url), "utf8"));
const newestHomes = worldState.buildings.filter(building =>
  String(building.type).endsWith("house") && Number(building.day) === Number(worldState.day));
const newestDistricts = [...new Set(newestHomes.map(building => building.district).filter(Boolean))];
const newestStreets = [...new Set(newestHomes.map(building => building.street).filter(Boolean))];

function watchPageErrors(page) {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  return errors;
}

async function waitForTown(page) {
  await expect(page.locator("#loading")).toBeHidden({ timeout: 45_000 });
}

test("homepage presents the live town and today's update", async ({ page }) => {
  const errors = watchPageErrors(page);
  await page.goto("/index.html");
  await expect(page.getByRole("heading", { name: "Followville" })).toBeVisible();
  await expect(page.locator("#statDay")).toHaveText(String(worldState.day));
  await expect(page.locator("#statPop")).toHaveText(String(worldState.pop));
  await expect(page.locator("#todaySummary")).toContainText(`${newestHomes.length} new homes in ${newestDistricts[0]}`);
  for (const street of newestStreets) await expect(page.locator("#todaySummary")).toContainText(street);
  await expect(page.locator("#mapPreview")).toBeVisible();
  await expect(page.locator("#todayBtn")).toHaveAttribute("href", "/today");
  expect(await page.locator("#mapPreview").evaluate(canvas => canvas.width > 100 && canvas.height > 100)).toBe(true);
  expect(errors).toEqual([]);
});

test("Today route opens the newest homes and returns home cleanly", async ({ page }) => {
  const errors = watchPageErrors(page);
  await page.goto("/today");
  await waitForTown(page);
  await expect(page.locator("#townMapPanel")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Today in Followville" })).toBeVisible();
  await expect(page.locator("#townMapRouteTitle")).toHaveText(`${newestHomes.length} new homes`);
  for (const district of newestDistricts) await expect(page.locator("#townMapRouteCopy")).toContainText(district);
  for (const street of newestStreets) await expect(page.locator("#townMapRouteCopy")).toContainText(street);
  await expect(page.locator("#townMapSelection")).toHaveClass(/active/);
  await page.getByRole("button", { name: "Close map" }).click();
  await expect(page).toHaveURL(/\/index\.html$/);
  expect(errors).toEqual([]);
});

test("shared house route can copy and visit a permanent address", async ({ page }) => {
  const errors = watchPageErrors(page);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "share", { configurable: true, value: undefined });
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async value => { window.__copiedHouseAddress = value; } }
    });
  });
  await page.goto("/house/29");
  await waitForTown(page);
  await expect(page.locator("#townMapPanel")).toBeVisible();
  await expect(page.locator("#townMapSearch")).toHaveValue("29");
  await expect(page.locator("#townMapSelectionTitle")).toContainText(/House #29|@/);
  await page.getByRole("button", { name: "share" }).click();
  await expect(page.locator("#townMapShareStatus")).toHaveText("Address copied.");
  expect(await page.evaluate(() => window.__copiedHouseAddress)).toBe("http://127.0.0.1:8765/house/29");
  await page.getByRole("button", { name: "visit this location" }).click();
  await expect(page.locator("#townMapPanel")).toBeHidden();
  await page.keyboard.press("Escape");
  await expect(page.locator("#pauseMenu")).toBeVisible();
  await expect(page).toHaveURL(/\/house\/29$/);
  await page.getByRole("button", { name: "leave town" }).click();
  await expect(page).toHaveURL(/\/index\.html$/);
  expect(errors).toEqual([]);
});

test("walking keyboard overlays close without trapping movement", async ({ page }) => {
  const errors = watchPageErrors(page);
  await page.goto("/town.html#walk");
  await waitForTown(page);
  await expect(page.locator("#startScreen")).toBeHidden();
  await expect(page.locator("body")).toHaveAttribute("data-hill-clearance", "pass");
  await expect(page.locator("body")).toHaveAttribute("data-storybook-walkable", "pass");
  await expect(page.locator("body")).toHaveAttribute("data-storybook-hitboxes", "pass");
  await expect(page.locator("body")).toHaveAttribute("data-kaleidoscope-statue", "pass");
  await page.keyboard.press("KeyT");
  await expect(page.locator("#chatPanel")).toHaveClass(/open/);
  await page.keyboard.press("Escape");
  await expect(page.locator("#chatPanel")).not.toHaveClass(/open/);
  await page.keyboard.press("KeyM");
  await expect(page.locator("#townMapPanel")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("#townMapPanel")).toBeHidden();
  await page.keyboard.press("Escape");
  await expect(page.locator("#pauseMenu")).toBeVisible();
  await expect(page.locator("#manageHomesBtn")).toContainText("manage my home");
  await page.getByRole("button", { name: "resume", exact: true }).click();
  await expect(page.locator("#pauseMenu")).toBeHidden();
  await expect(page).toHaveURL(/\/town\.html$/);
  await page.keyboard.press("Escape");
  await expect(page.locator("#pauseMenu")).toBeVisible();
  await page.getByRole("button", { name: "leave town" }).click();
  await expect(page).toHaveURL(/\/index\.html$/);
  expect(errors).toEqual([]);
});

test("unknown house addresses fail gracefully", async ({ page }) => {
  const errors = watchPageErrors(page);
  await page.goto("/house/9999");
  await waitForTown(page);
  await expect(page.getByRole("heading", { name: "Address unavailable" })).toBeVisible();
  await expect(page.locator("#townMapRouteCopy")).toContainText("not in the current town build");
  await expect(page.locator("#townMapEmpty")).toHaveText("No locations match that search.");
  expect(errors).toEqual([]);
});
