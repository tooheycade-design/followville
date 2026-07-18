import { devices, expect, test } from "@playwright/test";
import { readFileSync, statSync } from "node:fs";

const worldState = JSON.parse(readFileSync(new URL("../world_state.json", import.meta.url), "utf8"));
const townManifest = JSON.parse(readFileSync(new URL("../town_manifest.json", import.meta.url), "utf8"));
const fullTownBytes = statSync(new URL("../town.glb", import.meta.url)).size;
const { defaultBrowserType: _mobileBrowser, ...mobileDevice } = devices["iPhone 13"];
const newestHomes = worldState.buildings.filter(building =>
  String(building.type).endsWith("house") && Number(building.day) === Number(worldState.day));
const newestDistricts = [...new Set(newestHomes.map(building => building.district).filter(Boolean))];
const newestStreets = [...new Set(newestHomes.map(building => building.street).filter(Boolean))];
const allHomes = worldState.buildings.filter(building => String(building.type).endsWith("house"));
const mapStreetCount = new Set(allHomes.map(building => building.street || "Original town")).size;

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

test("a bare legacy town URL returns to the current homepage", async ({ page }) => {
  await page.goto("/town.html");
  await expect(page).toHaveURL(/\/index\.html$/);
  await expect(page.locator("#mapPreview")).toBeVisible();
  await expect(page.locator("#todaySummary")).toBeVisible();
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
  await page.getByRole("button", { name: "go to this house" }).click();
  await expect(page.locator("#townMapPanel")).toBeHidden();
  await page.keyboard.press("Escape");
  await expect(page.locator("#pauseMenu")).toBeVisible();
  await expect(page).toHaveURL(/\/house\/29$/);
  await page.getByRole("button", { name: "leave town" }).click();
  await expect(page).toHaveURL(/\/index\.html$/);
  expect(errors).toEqual([]);
});

test("walking keyboard overlays close without trapping movement", async ({ page }) => {
  test.setTimeout(180_000);
  const errors = watchPageErrors(page);
  await page.goto("/town.html#walk");
  await waitForTown(page);
  await expect(page.locator("#startScreen")).toBeHidden();
  await expect(page.locator("body")).toHaveAttribute("data-hill-clearance", "pass");
  await expect(page.locator("body")).toHaveAttribute("data-storybook-walkable", "pass");
  await expect(page.locator("body")).toHaveAttribute("data-storybook-hitboxes", "pass");
  await expect(page.locator("body")).toHaveAttribute("data-kaleidoscope-statue", "pass");
  await expect(page.locator("body")).toHaveAttribute("data-asset-mode", "streamed");
  await expect(page.locator("body")).toHaveAttribute("data-stream-manifest", "pass");
  const loadedChunks = (await page.locator("body").getAttribute("data-loaded-chunks") || "").split(",");
  expect(loadedChunks).toEqual(expect.arrayContaining(["original-town"]));
  const initialBytes = Number(await page.locator("body").getAttribute("data-stream-initial-bytes"));
  expect(initialBytes).toBe(townManifest.base.bytes + townManifest.chunks
    .filter(chunk => chunk.initial).reduce((sum, chunk) => sum + chunk.asset.bytes, 0));
  expect(initialBytes).toBeLessThan(fullTownBytes * 0.4);
  await expect(page.locator("#chatPanel")).toHaveClass(/feed-visible/);
  const chatFeedBox=await page.locator("#chatPanel").boundingBox();
  expect(chatFeedBox.x).toBeLessThan(30);
  expect(chatFeedBox.y).toBeLessThan(140);
  await page.keyboard.press("KeyT");
  await expect(page.locator("#chatPanel")).toHaveClass(/open/);
  await page.keyboard.press("Escape");
  await expect(page.locator("#chatPanel")).not.toHaveClass(/open/);
  await page.keyboard.press("KeyM");
  await expect(page.locator("#townMapPanel")).toBeVisible();
  await expect(page.locator("#townMapCanvas")).toBeVisible();
  await expect(page.locator("#townMapSearch")).toHaveAttribute("placeholder", /@owner/);
  await expect(page.locator("[data-map-street]")).toHaveCount(mapStreetCount);
  const newestStreet = newestStreets[0];
  const newestStreetHomes = allHomes.filter(building => building.street === newestStreet).length;
  await page.locator("#townMapSearch").fill(newestStreet);
  await expect(page.locator("[data-map-key]")).toHaveCount(newestStreetHomes);
  await page.locator("#townMapSearch").fill("#29");
  await expect(page.locator("[data-map-key]").first()).toContainText("House #29");
  await page.locator("#townMapSearch").fill("");
  await expect(page.locator("[data-map-street]")).toHaveCount(mapStreetCount);
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

test("Avatar Studio only offers the animated character library and persists it", async ({ page }) => {
  test.setTimeout(180_000);
  const errors = watchPageErrors(page);
  const avatarRequests=[];
  page.on("request",request=>{if(request.url().includes("/avatar_assets/"))avatarRequests.push(request.url());});
  await page.addInitScript(() => {
    if(sessionStorage.getItem("followville_test_seeded_avatar"))return;
    sessionStorage.setItem("followville_test_seeded_avatar","true");
    localStorage.setItem("followville_avatar_v1",JSON.stringify({
      version:1,skin:"cocoa",height:"tall",face:"defined",hair:"long",
      outfit:"field_jacket",hat:"ranger_hood",look:"custom"
    }));
  });
  await page.goto("/town.html#walk");
  await waitForTown(page);
  await expect(page.locator("body")).toHaveAttribute("data-camera-mode", "third-person");
  expect(Number(await page.locator("body").getAttribute("data-camera-distance"))).toBeGreaterThan(2);
  await expect(page.locator("body")).toHaveAttribute("data-avatar", /:casual_day_m$/);

  await page.keyboard.press("KeyV");
  await expect(page.locator("#avatarStudio")).toBeVisible();
  await expect(page.getByRole("heading", { name:"Make yourself at home" })).toBeVisible();
  await expect(page.getByRole("tab")).toHaveCount(2);
  await expect(page.getByRole("tab", { name:"Characters" })).toBeVisible();
  await expect(page.getByRole("tab", { name:"Body" })).toBeVisible();
  await expect(page.locator("#avatarPreviewCanvas")).toBeVisible();
  expect(await page.locator("#avatarPreviewCanvas").evaluate(canvas => canvas.width > 100 && canvas.height > 100)).toBe(true);
  await expect(page.locator("[data-avatar-kind='look']")).toHaveCount(37);
  await expect(page.locator(".avatar-look-thumb")).toHaveCount(37);
  await expect(page.locator("[data-avatar-kind='face'],[data-avatar-kind='hair'],[data-avatar-kind='outfit'],[data-avatar-kind='hat']")).toHaveCount(0);
  await page.locator("[data-avatar-kind='look'][data-avatar-id='wizard']").click();
  await page.getByRole("button", { name:"save avatar" }).click();
  await expect(page.locator("#avatarStudio")).toBeHidden();
  await expect(page.locator("body")).toHaveAttribute("data-avatar", /:wizard$/);
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("followville_avatar_v1")))).toMatchObject({
    version:1,look:"wizard"
  });

  await page.goto("/town.html#walk");
  await waitForTown(page);
  await expect(page.locator("body")).toHaveAttribute("data-avatar", /:wizard$/);
  expect(avatarRequests.some(url=>/\/(core\.glb|hair\/|outfit\/|hat\/)/.test(url))).toBe(false);
  expect(errors).toEqual([]);
});

test("player camera follows, right-drag orbits, wheel reaches first person, and A/D are correct", async ({ page }) => {
  test.setTimeout(420_000);
  const errors=watchPageErrors(page);
  await page.goto("/town.html#walk");
  await waitForTown(page);
  await expect(page.locator("#startScreen")).toBeHidden();
  await expect(page.locator("body")).toHaveAttribute("data-player-ready","true");
  await expect(page.locator("#crosshair")).toBeHidden();
  const positions=()=>page.locator("body").evaluate(body=>{
    const parse=name=>(body.dataset[name]||"0,0").split(",").map(Number);
    return {player:parse("playerPosition"),camera:parse("cameraPosition")};
  });
  const initial=await positions();

  await page.keyboard.press("Space");
  await expect(page.locator("body")).toHaveAttribute("data-jumping","true");
  await expect.poll(async()=>Number(await page.locator("body").getAttribute("data-jump-peak")),{timeout:15_000}).toBeGreaterThan(.25);
  await expect(page.locator("body")).not.toHaveAttribute("data-jumping",/./,{timeout:15_000});
  expect(Number(await page.locator("body").getAttribute("data-jump-height"))).toBe(0);

  await page.mouse.move(220,220);
  await page.mouse.move(520,360,{steps:5});
  const noDrag=await positions();
  expect(Math.hypot(noDrag.camera[0]-initial.camera[0],noDrag.camera[1]-initial.camera[1])).toBeLessThan(.2);

  await page.mouse.move(520,360);
  await page.mouse.down({button:"right"});
  await expect(page.locator("body")).toHaveAttribute("data-camera-grab","locked");
  expect(await page.evaluate(() => document.pointerLockElement?.tagName)).toBe("CANVAS");
  await page.mouse.move(700,310,{steps:6});
  await page.mouse.up({button:"right"});
  await expect(page.locator("body")).not.toHaveAttribute("data-camera-grab",/./);
  expect(await page.evaluate(() => document.pointerLockElement)).toBeNull();
  const orbited=await positions();
  expect(Math.hypot(orbited.camera[0]-initial.camera[0],orbited.camera[1]-initial.camera[1])).toBeGreaterThan(1);

  const forward=[orbited.player[0]-orbited.camera[0],orbited.player[1]-orbited.camera[1]];
  const length=Math.hypot(...forward);
  const screenRight=[-forward[1]/length,forward[0]/length];
  await page.keyboard.down("KeyD");await page.waitForTimeout(650);await page.keyboard.up("KeyD");
  const afterD=await positions();
  const dDelta=[afterD.player[0]-orbited.player[0],afterD.player[1]-orbited.player[1]];
  expect(dDelta[0]*screenRight[0]+dDelta[1]*screenRight[1]).toBeGreaterThan(1);
  await page.keyboard.down("KeyA");await page.waitForTimeout(650);await page.keyboard.up("KeyA");
  const afterA=await positions();
  const aDelta=[afterA.player[0]-afterD.player[0],afterA.player[1]-afterD.player[1]];
  expect(aDelta[0]*screenRight[0]+aDelta[1]*screenRight[1]).toBeLessThan(-1);

  const beforeForward=await positions();
  await page.keyboard.down("KeyW");await page.waitForTimeout(1500);await page.keyboard.up("KeyW");
  const afterForward=await positions();
  // The exact distance varies when the terrain-aware collider pass nudges the
  // avatar around nearby curbs or props; the camera must still travel with it.
  expect(Math.hypot(afterForward.player[0]-beforeForward.player[0],afterForward.player[1]-beforeForward.player[1])).toBeGreaterThan(2);
  expect(Math.hypot(afterForward.camera[0]-beforeForward.camera[0],afterForward.camera[1]-beforeForward.camera[1])).toBeGreaterThan(2);

  // Looking nearly straight up must slide the camera along the walk surface;
  // the terrain itself cannot become a camera obstruction.
  await page.mouse.move(640,650);
  await page.mouse.down({button:"right"});
  await page.mouse.move(640,30,{steps:8});
  await expect.poll(async()=>Number(await page.locator("body").getAttribute("data-camera-pitch"))).toBeGreaterThan(1.3);
  expect(Number(await page.locator("body").getAttribute("data-camera-ground-clearance"))).toBeGreaterThanOrEqual(.4);
  await page.mouse.up({button:"right"});
  // Pointer-lock ignores out-of-viewport coordinates in headless Chromium.
  // Two ordinary top-to-bottom grabs exercise the same real input path and
  // cover the full pitch range without manufacturing a DOM mouse event.
  for(let drag=0;drag<2;drag++){
    await page.mouse.move(640,30);
    await page.mouse.down({button:"right"});
    await page.mouse.move(640,650,{steps:8});
    await page.mouse.up({button:"right"});
  }
  await expect.poll(async()=>Number(await page.locator("body").getAttribute("data-camera-pitch"))).toBeLessThan(-1.3);

  await page.mouse.wheel(0,-2000);
  await expect(page.locator("body")).toHaveAttribute("data-camera-mode","first-person");
  await expect(page.locator("body")).toHaveAttribute("data-first-person-look","locked");
  expect(await page.evaluate(() => document.pointerLockElement?.tagName)).toBe("CANVAS");
  const firstPersonYaw=Number(await page.locator("body").getAttribute("data-camera-yaw"));
  await page.mouse.move(860,380,{steps:5});
  expect(Math.abs(Number(await page.locator("body").getAttribute("data-camera-yaw"))-firstPersonYaw)).toBeGreaterThan(.05);
  await page.mouse.wheel(0,1500);
  await expect(page.locator("body")).toHaveAttribute("data-camera-mode","third-person");
  expect(await page.evaluate(() => document.pointerLockElement)).toBeNull();
  expect(errors).toEqual([]);
});

test("visiting a house loads its district before teleporting", async ({ page }) => {
  const errors = watchPageErrors(page);
  const willowHome = allHomes.find(building => building.district === "Willow Hills");
  expect(willowHome).toBeTruthy();
  await page.goto(`/house/${willowHome.seed}`);
  await waitForTown(page);
  await expect(page.locator("#townMapPanel")).toBeVisible();
  await expect(page.locator("body")).not.toHaveAttribute("data-loaded-chunks", /willow-hills/);
  await page.getByRole("button", { name: "go to this house" }).click();
  await expect(page.locator("#townMapPanel")).toBeHidden({ timeout: 30_000 });
  await expect(page.locator("body")).toHaveAttribute("data-loaded-chunks", /willow-hills/);
  await expect(page.locator("body")).not.toHaveAttribute("data-loaded-chunks", /kaleidoscope-crest/, { timeout:10_000 });
  expect(Number(await page.locator("body").getAttribute("data-streamed-chunk-unloads"))).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});

test("complete-town fallback remains usable if the stream manifest is unavailable", async ({ page }) => {
  const errors = watchPageErrors(page);
  await page.route("**/town_manifest.json", route => route.abort());
  await page.goto("/town.html#walk");
  await waitForTown(page);
  await expect(page.locator("body")).toHaveAttribute("data-stream-manifest", "fallback");
  await expect(page.locator("body")).toHaveAttribute("data-asset-mode", "fallback");
  await expect(page.locator("body")).toHaveAttribute("data-loaded-chunks", "full");
  await expect(page.locator("body")).toHaveAttribute("data-claim-tag-roof-clearance", "1.25");
  await expect(page.locator("body")).toHaveAttribute("data-storybook-hitboxes", "pass");
  await expect(page.locator("body")).toHaveAttribute("data-kaleidoscope-statue", "pass");
  expect(errors).toEqual([]);
});

test.describe("mobile town", () => {
  test.use(mobileDevice);

  test("touch controls and the map remain usable with streamed districts", async ({ page }) => {
    test.setTimeout(300_000);
    const errors = watchPageErrors(page);
    await page.goto("/town.html#walk");
    await waitForTown(page);
    await expect(page.locator("body")).toHaveAttribute("data-asset-mode", "streamed");
    await expect(page.locator("#lookZone")).toBeVisible();
    await expect(page.locator("#joystickZone")).toBeVisible();
    await expect(page.locator("#jumpBtn")).toBeVisible();
    const readPositions=()=>page.locator("body").evaluate(body=>({
      player:(body.dataset.playerPosition||"0,0").split(",").map(Number),
      camera:(body.dataset.cameraPosition||"0,0").split(",").map(Number)
    }));
    const beforeTwoThumb=await readPositions();
    const joystickBox=await page.locator("#joystickZone").boundingBox();
    const lookBox=await page.locator("#lookZone").boundingBox();
    const cdp=await page.context().newCDPSession(page);
    const joy={x:joystickBox.x+joystickBox.width/2,y:joystickBox.y+joystickBox.height/2};
    const look={x:lookBox.x+lookBox.width*.68,y:lookBox.y+lookBox.height*.48};
    await cdp.send("Input.dispatchTouchEvent",{type:"touchStart",touchPoints:[joy]});
    await cdp.send("Input.dispatchTouchEvent",{type:"touchStart",touchPoints:[joy,look]});
    await cdp.send("Input.dispatchTouchEvent",{type:"touchMove",touchPoints:[
      {x:joy.x,y:joy.y-36},{x:look.x+70,y:look.y-8}
    ]});
    await page.waitForTimeout(700);
    await cdp.send("Input.dispatchTouchEvent",{type:"touchEnd",touchPoints:[]});
    const afterTwoThumb=await readPositions();
    expect(Math.hypot(afterTwoThumb.player[0]-beforeTwoThumb.player[0],afterTwoThumb.player[1]-beforeTwoThumb.player[1])).toBeGreaterThan(1);
    const beforeOffset=[beforeTwoThumb.camera[0]-beforeTwoThumb.player[0],beforeTwoThumb.camera[1]-beforeTwoThumb.player[1]];
    const afterOffset=[afterTwoThumb.camera[0]-afterTwoThumb.player[0],afterTwoThumb.camera[1]-afterTwoThumb.player[1]];
    expect(Math.hypot(afterOffset[0]-beforeOffset[0],afterOffset[1]-beforeOffset[1])).toBeGreaterThan(.5);
    await page.locator("#jumpBtn").tap();
    await expect(page.locator("body")).toHaveAttribute("data-jumping","true");
    await expect(page.locator("body")).not.toHaveAttribute("data-jumping",/./,{timeout:1500});
    await page.getByRole("button", { name: /town map/i }).click();
    await expect(page.locator("#townMapPanel")).toBeVisible();
    await page.getByRole("button", { name: "Close map" }).click();
    await expect(page.locator("#townMapPanel")).toBeHidden();
    await expect(page.locator("#joystickZone")).toBeVisible();
    await page.getByRole("button", { name:"avatar", exact:true }).click();
    await expect(page.locator("#avatarStudio")).toBeVisible();
    await page.getByRole("button", { name:"Close avatar studio" }).click();
    await expect(page.locator("#avatarStudio")).toBeHidden();
    await expect(page.locator("#joystickZone")).toBeVisible();
    expect(errors).toEqual([]);
  });
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
