/* Runs the REAL inventory panel code out of town.html against jsdom.
 *
 * The Playwright suite is the real browser check, but it needs a GPU-ish
 * Chromium and several minutes to load the town. This runs in about a second
 * with no browser at all, so panel-rendering regressions surface immediately.
 *
 * It deliberately extracts the shipped source from town.html rather than
 * re-declaring a copy: a copy would keep passing after the real code broke.
 *
 *   node tests/inventory_panel_test.mjs     (needs: npm install jsdom)
 */
import { readFileSync, writeFileSync, rmSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { JSDOM } from "jsdom";

const here = dirname(fileURLToPath(import.meta.url));
const townPath = join(here, "..", "town.html");
const town = readFileSync(townPath, "utf8");

let failures = 0;
const ok = (name, cond, detail = "") => {
  if (cond) console.log(`  pass  ${name}`);
  else { failures++; console.log(`  FAIL  ${name} ${detail}`); }
};

/* ── Pull the shipped markup and the shipped script block out of town.html ── */
const markup = town.match(/<section id="inventoryPanel"[\s\S]*?<\/section>/);
ok("inventory panel markup found in town.html", !!markup);

const script = town.match(
  /\/\* ─── Inventory System v1 ───[\s\S]*?(?=\/\* ─── Fishing Pond)/);
ok("inventory script block found in town.html", !!script);
if (!markup || !script){ process.exit(1); }

const dom = new JSDOM(`<!doctype html><html><body>
  ${markup[0]}
  <button id="pauseInventoryBtn"></button>
  <button id="worldFishingBag" hidden></button>
  <div id="pauseMenu"></div>
</body></html>`, { pretendToBeVisual: true, url: "https://followville.test/town.html" });

const { window } = dom;
global.window = window;
global.document = window.document;
global.requestAnimationFrame = cb => cb();

/* Minimal stand-ins for the town globals the panel touches. Each one is
   something the panel only reads or toggles; none of them affect the rendering
   assertions below. */
const stubEl = () => ({ style: {}, classList: { add(){}, remove(){} } });
const scope = {
  sb: null,
  gameRunning: false,
  isTouch: false,
  // ?local=1 in the real page. On for this harness so the QA hook is built and
  // can be asserted on below.
  localDesignPreview: true,
  clearMovementInput(){},
  resumeDesktopWalking(){},
  resumeWalkingWithoutPointerLock(){},
  crosshair: stubEl(), hint: stubEl(), lookZone: stubEl(),
  joystickZone: stubEl(), runBtn: stubEl(), jumpBtn: stubEl(),
  pauseMenu: window.document.getElementById("pauseMenu")
};

const inventoryModule = join(here, "..", "inventory-system.js");
/* `gameRunning` is reassigned by openInventory, so these have to be `let` —
   destructuring them as const is what a naive harness gets wrong. */
const src = `
  import { createInventoryStore, inventoryRows, inventoryTotal,
           inventorySpeciesCount, inventoryIsEmpty, rollFishOfRarity,
           fishById } from ${JSON.stringify(pathToFileURL(inventoryModule).href)};
  let { sb, gameRunning, isTouch, localDesignPreview, clearMovementInput,
        resumeDesktopWalking, resumeWalkingWithoutPointerLock, crosshair, hint,
        lookZone, joystickZone, runBtn, jumpBtn, pauseMenu } = globalThis.__scope;
  ${script[0]}
  globalThis.__api = { openInventory, closeInventory, inventoryOpen,
                       renderInventory, inventoryStore, publishInventoryState };
`;

globalThis.__scope = scope;
/* localStorage: jsdom provides one, but the module defaults to globalThis. */
global.localStorage = window.localStorage;

/* A real temp file, not a data: URL — a stack trace from a base64 blob is
   unreadable, and this harness exists to make failures obvious. */
const tmp = join(tmpdir(), `followville_inventory_harness_${process.pid}.mjs`);
writeFileSync(tmp, src);
try { await import(pathToFileURL(tmp).href); }
finally { rmSync(tmp, { force: true }); }
const api = globalThis.__api;
const body = window.document.body;
const grid = window.document.getElementById("inventoryGrid");
const emptyNote = window.document.getElementById("inventoryEmpty");
const sub = window.document.getElementById("inventorySub");
const saveNote = window.document.getElementById("inventorySaveNote");

console.log("\nempty state");
api.openInventory();
ok("panel opens", api.inventoryOpen());
ok("empty note shown when nothing is caught", emptyNote.hidden === false);
ok("grid hidden when nothing is caught", grid.hidden === true);
ok("body advertises a zero total", body.dataset.inventoryTotal === "0", body.dataset.inventoryTotal);
ok("guest store reported as device", body.dataset.inventoryStore === "device");
api.closeInventory(false);

console.log("\nstacking");
const first = api.inventoryStore.recordCatch("pond_perch");
ok("first catch flagged as a new species", first.isNew === true);
const second = api.inventoryStore.recordCatch("pond_perch");
ok("second identical catch stacks rather than appending", second.count === 2 && second.isNew === false);
api.inventoryStore.recordCatch("kaleidoscope_koi");
ok("body total counts every fish", body.dataset.inventoryTotal === "3", body.dataset.inventoryTotal);
ok("body species counts distinct fish", body.dataset.inventorySpecies === "2", body.dataset.inventorySpecies);

console.log("\npopulated panel");
api.openInventory();
ok("empty note hidden once something is caught", emptyNote.hidden === true);
ok("grid visible once something is caught", grid.hidden === false);
ok("every catalog slot is rendered", grid.children.length === 13, String(grid.children.length));
const discovered = [...grid.children].filter(el => !el.classList.contains("locked"));
ok("exactly the caught species are unlocked", discovered.length === 2, String(discovered.length));
ok("discovered slots sort to the top",
  !grid.children[0].classList.contains("locked") && !grid.children[1].classList.contains("locked"));
ok("stack count is displayed as a multiplier",
  [...grid.children].some(el => el.querySelector(".inv-count").textContent === "×2"));
ok("locked slots hide the species name",
  grid.children[12].querySelector(".inv-name").textContent === "Not yet caught");
ok("locked slots still show a dash, not a zero",
  grid.children[12].querySelector(".inv-count").textContent === "—");
ok("subtitle reports both numbers", /3 fish caught · 2 of 13 species/.test(sub.textContent), sub.textContent);
ok("guest is told where the save lives", /this device/i.test(saveNote.textContent), saveNote.textContent);
ok("slots carry an accessible label",
  /caught/.test(grid.children[0].getAttribute("aria-label")), grid.children[0].getAttribute("aria-label"));

console.log("\nunknown ids");
const bogus = api.inventoryStore.recordCatch("shark");
ok("an unknown fish id is ignored, not stored", bogus.count === 0 && body.dataset.inventoryTotal === "3");

console.log("\npersistence");
ok("guest catches were written to localStorage",
  JSON.parse(window.localStorage.getItem("followville_inventory_v1")).fish.pond_perch === 2);

console.log("\nmaintainer QA hook");
ok("QA hook is exposed under ?local=1", typeof window.__followvilleInventoryQA?.recordCatch === "function");

console.log("\nclose");
api.closeInventory(true);
ok("panel closes", !api.inventoryOpen());
ok("open flag cleared from body", body.dataset.inventoryOpen === undefined);

console.log(failures ? `\n${failures} FAILED\n` : "\nall inventory panel checks passed\n");
process.exit(failures ? 1 : 0);
