/* Followville Inventory System v1 — fish only.
 *
 * Scope on purpose: this module owns the fish catalog, the stacking rules, the
 * normalized payload shape, and the two stores (guest localStorage, signed-in
 * Supabase). It knows nothing about THREE, the town scene, or the DOM. town.html
 * owns the panel, the open/close transition, and the fishing hook-up.
 *
 * WEB-ONLY. Nothing here reads or writes world_state.json, town.glb, a district
 * chunk, or the authoritative Blend. An inventory is a property of a *player*,
 * not of the town, so it lives on profiles — never on a house or a claim.
 *
 * Stacking: catching a second Pond Perch does not append a second record, it
 * turns the existing one into "x2". Counts (not individual catch records) are
 * also exactly what a future Follow Bucks economy needs to price a stack, so
 * the shape is forward-compatible without a migration rewrite.
 *
 * Honest limitation, do not paper over it: the fishing game runs entirely in
 * the browser, so the server cannot tell a real catch from a forged RPC call.
 * The RPC is add-only and rate-shaped, which bounds the damage to "someone gave
 * themselves fish", never "someone edited or deleted anything". Anti-cheat here
 * would require moving the fishing simulation server-side, which v1 does not do.
 */

export const INVENTORY_VERSION = 1;
export const INVENTORY_STORAGE_KEY = "followville_inventory_v1";

/* Per-species ceiling. Also the reason the whole JSON stays comfortably under
   the 1024-byte column constraint even with every species maxed. */
export const MAX_PER_SPECIES = 999;
/* Largest single add. One catch sends 1; a guest-to-account merge sends a whole
   stash at once, and this is the ceiling on that. */
export const MAX_ADD_PER_CALL = 200;

/* Rarity tiers mirror FISHING_PROFILES in town.html. The colors are the same
   values so a rarity chip in the inventory matches the chip on the catch card.
   Change one, change the other. */
export const FISH_RARITIES = {
  Common:    { order: 0, color: "#587d88" },
  Uncommon:  { order: 1, color: "#43875f" },
  Rare:      { order: 2, color: "#3977b7" },
  Legendary: { order: 3, color: "#c07a22" },
  Mythical:  { order: 4, color: "#9b4bb3" }
};

/* The catalog. IDs are stable and permanent: they are written into saved player
   data and into the SQL allowlist, so an ID is never renamed or reused. Display
   names are free to change.
 *
 * Adding a fish means keeping three lists in sync, the same discipline the
 * interior catalog uses:
 *   1. this array,
 *   2. the allowlist inside add_to_my_inventory in supabase_schema.sql,
 *   3. the same allowlist in a NEW migration — never rewrite an applied one.
 */
export const FISH_CATALOG = [
  { id:"pond_perch",         name:"Pond Perch",         rarity:"Common",    color:"#edbf59", note:"Always biting near the dock posts." },
  { id:"meadow_minnow",      name:"Meadow Minnow",      rarity:"Common",    color:"#d9e3a4", note:"Travels in nervous little crowds." },
  { id:"dock_sunfish",       name:"Dock Sunfish",       rarity:"Common",    color:"#f0ab4d", note:"Flat, round and completely unbothered." },
  { id:"rusty_carp",         name:"Rusty Carp",         rarity:"Uncommon",  color:"#e77d4f", note:"Older than the pond it lives in." },
  { id:"willow_bass",        name:"Willow Bass",        rarity:"Uncommon",  color:"#7fae6a", note:"Holds under the reeds until dusk." },
  { id:"speckled_trout",     name:"Speckled Trout",     rarity:"Uncommon",  color:"#c9906b", note:"Freckled all the way down its back." },
  { id:"bluebell_pike",      name:"Bluebell Pike",      rarity:"Rare",      color:"#6fc6e8", note:"All teeth, no manners." },
  { id:"glass_eel",          name:"Glass Eel",          rarity:"Rare",      color:"#bfe6ea", note:"You can read the dock through it." },
  { id:"moonlit_catfish",    name:"Moonlit Catfish",    rarity:"Rare",      color:"#8f93c4", note:"Sits on the bottom, thinking." },
  { id:"golden_sturgeon",    name:"Golden Sturgeon",    rarity:"Legendary", color:"#e8a444", note:"Armored, ancient, faintly smug." },
  { id:"founders_koi",       name:"Founder's Koi",      rarity:"Legendary", color:"#f2c8a0", note:"Said to predate the first house." },
  { id:"kaleidoscope_koi",   name:"Kaleidoscope Koi",   rarity:"Mythical",  color:"#c781f1", note:"Every scale a different afternoon." },
  { id:"followville_phantom",name:"Followville Phantom",rarity:"Mythical",  color:"#9fb6ff", note:"Most anglers only ever see the ripple." }
];

const FISH_BY_ID = new Map(FISH_CATALOG.map(fish => [fish.id, fish]));
const FISH_BY_RARITY = FISH_CATALOG.reduce((acc, fish) => {
  (acc[fish.rarity] = acc[fish.rarity] || []).push(fish);
  return acc;
}, {});

export function fishById(id){ return FISH_BY_ID.get(String(id)) || null; }
export function fishOfRarity(rarity){ return FISH_BY_RARITY[rarity] || []; }
export function isKnownFish(id){ return FISH_BY_ID.has(String(id)); }

/** Pick a species inside an already-rolled rarity tier. The rarity roll stays
 *  in town.html where the difficulty tuning lives; this only chooses which
 *  fish of that tier showed up. */
export function rollFishOfRarity(rarity, random = Math.random){
  const pool = fishOfRarity(rarity);
  if (!pool.length) return null;
  return pool[Math.min(pool.length - 1, Math.floor(random() * pool.length))];
}

function clampCount(value){
  const n = Math.floor(Number(value));
  if (!Number.isFinite(n) || n < 1) return 0;
  return Math.min(MAX_PER_SPECIES, n);
}

/** The single source of truth for the payload shape. Anything that has been
 *  through here is safe to store, send, or render. Unknown IDs are dropped
 *  rather than throwing: a client running older code should still be able to
 *  read a newer server payload instead of showing an empty inventory. */
export function normalizeInventory(raw){
  const out = { version: INVENTORY_VERSION, fish: {} };
  const source = raw && typeof raw === "object" ? (raw.fish && typeof raw.fish === "object" ? raw.fish : {}) : {};
  for (const id of Object.keys(source)){
    if (!FISH_BY_ID.has(id)) continue;
    const count = clampCount(source[id]);
    if (count > 0) out.fish[id] = count;
  }
  return out;
}

export function emptyInventory(){ return { version: INVENTORY_VERSION, fish: {} }; }

export function inventoryIsEmpty(inv){
  return Object.keys(normalizeInventory(inv).fish).length === 0;
}

/** Total fish caught, all species. */
export function inventoryTotal(inv){
  const fish = normalizeInventory(inv).fish;
  return Object.values(fish).reduce((sum, n) => sum + n, 0);
}

/** Distinct species discovered — the "collection" number worth screenshotting. */
export function inventorySpeciesCount(inv){
  return Object.keys(normalizeInventory(inv).fish).length;
}

/** Merge b into a, additively, respecting the per-species ceiling. Additive is
 *  deliberate: there is no code path in this system that lowers a count, so a
 *  bad merge can never destroy a player's catches. */
export function mergeInventories(a, b){
  const left = normalizeInventory(a);
  const right = normalizeInventory(b);
  const out = { version: INVENTORY_VERSION, fish: { ...left.fish } };
  for (const [id, count] of Object.entries(right.fish)){
    out.fish[id] = Math.min(MAX_PER_SPECIES, (out.fish[id] || 0) + count);
  }
  return out;
}

/** Apply one catch locally and report whether it is a first-of-species, so the
 *  UI can say "new!" without recomputing anything. */
export function addCatch(inv, fishId, amount = 1){
  const normalized = normalizeInventory(inv);
  if (!FISH_BY_ID.has(String(fishId))) return { inventory: normalized, isNew: false, count: 0 };
  const id = String(fishId);
  const prior = normalized.fish[id] || 0;
  const next = Math.min(MAX_PER_SPECIES, prior + Math.max(1, Math.floor(amount)));
  normalized.fish[id] = next;
  return { inventory: normalized, isNew: prior === 0, count: next };
}

/** Catalog order, but discovered species first — a full-looking shelf reads
 *  better than a wall of locked slots. Ties keep catalog order so the grid
 *  never reshuffles under the player between opens. */
export function inventoryRows(inv){
  const fish = normalizeInventory(inv).fish;
  return FISH_CATALOG.map((entry, index) => ({
    ...entry,
    count: fish[entry.id] || 0,
    discovered: (fish[entry.id] || 0) > 0,
    rarityColor: FISH_RARITIES[entry.rarity]?.color || "#587d88",
    index
  })).sort((a, b) => (Number(b.discovered) - Number(a.discovered)) || (a.index - b.index));
}

/* ─── Guest store ───
   Guests keep an inventory on the device, exactly like avatars do. It is also
   the failure buffer for signed-in players: if the RPC errors, the catch lands
   here and merges on the next successful sync, so a catch is never lost to a
   dropped connection. */
export function loadDeviceInventory(storage = globalThis.localStorage){
  try { return normalizeInventory(JSON.parse(storage.getItem(INVENTORY_STORAGE_KEY) || "null")); }
  catch (_) { return emptyInventory(); }
}

export function saveDeviceInventory(inv, storage = globalThis.localStorage){
  try { storage.setItem(INVENTORY_STORAGE_KEY, JSON.stringify(normalizeInventory(inv))); return true; }
  catch (_) { return false; }
}

export function clearDeviceInventory(storage = globalThis.localStorage){
  try { storage.setItem(INVENTORY_STORAGE_KEY, JSON.stringify(emptyInventory())); return true; }
  catch (_) { return false; }
}

/** Split an additive payload into RPC-sized chunks. Only a very long guest
 *  session could exceed one call, but silently dropping the overflow would lose
 *  real catches, so chunk instead of clamp. */
export function chunkAddPayload(inv, limit = MAX_ADD_PER_CALL){
  const fish = normalizeInventory(inv).fish;
  const chunks = [];
  let current = {};
  let total = 0;
  for (const [id, count] of Object.entries(fish)){
    let remaining = count;
    while (remaining > 0){
      const take = Math.min(remaining, limit - total);
      if (take > 0){
        current[id] = (current[id] || 0) + take;
        total += take;
        remaining -= take;
      }
      if (total >= limit){ chunks.push(current); current = {}; total = 0; }
    }
  }
  if (total > 0) chunks.push(current);
  return chunks;
}

/* ─── Store ───
   One object town.html holds. It hides "am I signed in" from every caller, so
   the fishing code just says `store.recordCatch(id)` and never branches on auth.

   rpc(name, args) is injected rather than importing supabase here: this module
   stays testable with no network and no client library. */
export function createInventoryStore({ rpc = null, storage = globalThis.localStorage, onChange = () => {} } = {}){
  let signedIn = false;
  let current = loadDeviceInventory(storage);
  let syncing = false;

  function emit(){ onChange(snapshot()); }
  function snapshot(){ return normalizeInventory(current); }

  /* Persist locally whenever we are a guest, or whenever a server write failed.
     A signed-in player whose writes are succeeding leaves no local copy behind,
     so signing in on a shared computer cannot hand your fish to the next user. */
  function persistLocal(inv){ saveDeviceInventory(inv, storage); }

  async function pushAdd(payload){
    if (!rpc) return false;
    const chunks = chunkAddPayload({ version: INVENTORY_VERSION, fish: payload });
    for (const chunk of chunks){
      if (!Object.keys(chunk).length) continue;
      const { data, error } = await rpc("add_to_my_inventory", { p_items: chunk });
      if (error) return false;
      if (data) current = normalizeInventory(data.inventory ?? data);
    }
    return true;
  }

  return {
    get(){ return snapshot(); },
    isSignedIn(){ return signedIn; },

    /** Called once per landed fish. Returns the same shape as addCatch so the
     *  catch card can show "new!" and the running count immediately — the UI
     *  never waits on the network. */
    recordCatch(fishId, amount = 1){
      const applied = addCatch(current, fishId, amount);
      current = applied.inventory;
      emit();
      if (signedIn && rpc){
        pushAdd({ [String(fishId)]: Math.max(1, Math.floor(amount)) }).then(ok => {
          if (!ok){
            /* Server refused or the network dropped. Buffer locally so the next
               successful sync carries it up. */
            persistLocal(mergeInventories(loadDeviceInventory(storage), { fish: { [String(fishId)]: amount } }));
          }
          emit();
        });
      } else {
        persistLocal(current);
      }
      return applied;
    },

    /** Called from refreshMyStatus. `profileInventory` is profiles.inventory as
     *  returned by my_status. Signing in merges the device stash up exactly once
     *  and then clears it, so a guest who plays before signing up keeps the fish
     *  they caught — and cannot replay that stash into a second account. */
    async syncFromProfile(profileInventory, hasSession){
      if (syncing) return snapshot();
      syncing = true;
      try {
        signedIn = !!hasSession;
        if (!signedIn){
          current = loadDeviceInventory(storage);
          emit();
          return snapshot();
        }
        const server = normalizeInventory(profileInventory);
        const local = loadDeviceInventory(storage);
        current = server;
        if (!inventoryIsEmpty(local)){
          const ok = await pushAdd(local.fish);
          if (ok) clearDeviceInventory(storage);
          else current = mergeInventories(server, local);
        }
        emit();
        return snapshot();
      } finally {
        syncing = false;
      }
    },

    /** Signing out drops back to whatever this device holds. It does not copy
     *  the account's fish down — those belong to the account. */
    signOut(){
      signedIn = false;
      current = loadDeviceInventory(storage);
      emit();
      return snapshot();
    }
  };
}
