# Followville Inventory System v1

Status: built 2026-08-10, **not yet released**. The migration has been rehearsed
against a real PostgreSQL engine but has **not** been applied to the live
Supabase project. See "Before release" at the bottom.

Scope is deliberately one thing: **fish**. The pond has existed since Day 25
with a comment in `town.html` reading "catches remain session-only until
Followville has an inventory". This is that inventory and nothing more. No
currency, no shop, no trading, no found items, no equipment.

## Player experience

- Every landed fish is kept. Catching a second Pond Perch turns the existing
  entry into `×2` rather than adding a second row.
- Fish now have **species**, not just rarity tiers. The five tiers are unchanged
  and still own all difficulty tuning; a species roll inside the rolled tier
  decides which fish turned up, and lends the fight card and the in-world catch
  mesh its colour. "You landed a Bluebell Pike" reads as a creature; "you landed
  a Rare fish" read as a database row.
- The panel opens with `I`, from **my inventory** in the pause menu, or from
  **see my inventory** on the fishing HUD — which appears only in the moment
  after a fish is landed, and is not a permanent HUD button.
- All 13 species always show. Undiscovered ones are dashed, greyed and labelled
  "Not yet caught", so the panel reads as a collection log with somewhere to go
  rather than a bag that starts empty.
- Discovered species sort to the top; ties keep catalog order, so the grid never
  reshuffles under the player between opens.
- **Guests get a real inventory**, saved on the device. Signing in merges that
  stash into the account once and then clears it, so playing before you sign up
  is never wasted. The footer says plainly which of the two is happening.
- No new top-right HUD button. That stack is already five deep and `town.html`
  carries a comment about it becoming "a ragged staircase down a third of the
  screen"; the key, the pause menu and the contextual fishing button are enough.

## The catalog

13 species across the five existing rarity tiers:

| Rarity | Species |
| --- | --- |
| Common | Pond Perch, Meadow Minnow, Dock Sunfish |
| Uncommon | Rusty Carp, Willow Bass, Speckled Trout |
| Rare | Bluebell Pike, Glass Eel, Moonlit Catfish |
| Legendary | Golden Sturgeon, Founder's Koi |
| Mythical | Kaleidoscope Koi, Followville Phantom |

These names are a first pass and are **safe to rename** — display names are not
stored anywhere. **IDs are permanent**: they are written into saved player data
and into the SQL allowlist, so an ID is never renamed or reused.

Adding a fish means keeping three lists in sync, the same discipline the
interior catalog uses:

1. `FISH_CATALOG` in `inventory-system.js`,
2. the allowlist inside `followville_inventory_is_valid` in `supabase_schema.sql`,
3. the same allowlist in a **new** migration — never rewrite an applied one.

## Runtime architecture

`inventory-system.js` owns the catalog, the stacking rules, the normalized
payload shape, and both stores. It imports nothing — no THREE, no DOM, no
Supabase client — so it is testable with no browser and no network. `town.html`
owns the panel, the open/close transition, and the one call from the fishing
payoff.

The store hides "am I signed in" from every caller: the fishing code says
`inventoryStore.recordCatch(id)` and never branches on auth.

**This is a `[WEB]` change in the project's sense, but not the usual kind.** It
adds no geometry and no scenery, so there is nothing for `export_web.py` to
carry over. It reads and writes no `world_state.json`, no `town.glb`, no
district chunk and no Blend. An inventory belongs to a *player*, so it lives on
`profiles` — not on a house, not on a claim. Guests, unverified accounts and
non-homeowners all have one.

Runtime state is exposed as `data-*` on `<body>` (`data-inventory-total`,
`data-inventory-species`, `data-inventory-store`, `data-inventory-open`) so the
Playwright suite asserts on attributes rather than module internals.

## Persistence and security

Saved shape, on `profiles.inventory`:

```json
{"version":1,"fish":{"pond_perch":4,"kaleidoscope_koi":1}}
```

Counts, not individual catch records. That is also exactly what a future Follow
Bucks economy needs to price a stack, so the shape is forward-compatible
without a migration rewrite.

`supabase_migrations/20260810_inventory_system_v1.sql` adds only the
`inventory` column, the `profiles_inventory_valid` constraint, the
`followville_inventory_is_valid` helper, a column-level `UPDATE (inventory)`
grant, and the `add_to_my_inventory(jsonb)` RPC. It does not touch houses,
claims, ownership, verification, admin status, world state, population or
geometry. Existing rows arrive valid via the column default and are not
rewritten.

Three things worth keeping:

- **Add-only.** Nothing in the schema lowers or clears a count. The client asks
  for an increment; it can never SET one. A client bug, a double-fire or a
  hostile caller can inflate a stack but can never destroy a player's catches.
  A Follow Bucks spend path will need a decrement — that is a later migration
  with its own audit trail, not an edit to this one.
- **The `revoke` is table-wide.** `grant update (avatar, inventory)` re-grants
  both columns together. Dropping `avatar` from that list would silently break
  avatar saving; the migration test asserts it survived.
- **CHECK constraints cannot contain subqueries**, and validating "every key of
  a nested object is in an allowlist" needs one. `followville_inventory_is_valid`
  is an immutable helper for exactly that reason, and it keeps the allowlist in
  one place shared by the constraint and the RPC.

The existing `profiles_own_avatar_update` policy is reused rather than
duplicated. Its row scope — own row, `UPDATE`, `authenticated` — is identical
for both columns; the column grant is what narrows it. The name is historical.

**Honest limitation, do not paper over it:** the fishing game runs entirely in
the browser, so the server cannot distinguish a real catch from a forged RPC
call. The RPC is allowlisted, add-only, capped at 200 per call and 999 per
species, which bounds the damage to "someone gave themselves fish" and never
"someone edited or deleted anything". Real anti-cheat would mean moving the
fishing simulation server-side, which v1 does not do. If fish ever become
worth money, revisit this **before** the money, not after.

## Verification

Two fast local checks, both runnable with `pnpm test:inventory`:

- `tests/inventory_migration_test.mjs` applies the migration to a real
  PostgreSQL 18 engine (PGlite, Postgres compiled to wasm) and asserts 24
  behaviours: stacking, bulk merge, the 999 ceiling, eight rejection cases,
  signed-out refusal, the CHECK holding without the RPC, the grant set, and
  idempotent re-run preserving saved fish.
- `tests/inventory_panel_test.mjs` extracts the **shipped** panel source out of
  `town.html` and runs it against jsdom — 26 checks on empty state, stacking
  display, sort order, locked slots, accessibility labels and localStorage. It
  extracts rather than copies deliberately: a copy would keep passing after the
  real code broke.

Browser coverage lives in `tests/followville.spec.mjs`: the existing fishing
story now asserts the catch reaches the inventory, and a new test covers the
empty state, the `I` key, stacking, and guest persistence across a reload. Run
the full `pnpm test:e2e` before release.

The local fishing audit route (`?local=1&view=fishing`) pins the species to
Pond Perch for the same reason it already pins the rarity to Common: automated
input needs one deterministic fish to assert on. `window.__followvilleInventoryQA`
is gated behind `?local=1` exactly like the fishing and terrain probes.

## Before release

Not yet done, and required:

1. Apply the migration to the live project, first inside a rolled-back
   transaction, the way the interior and avatar migrations were rehearsed.
2. Record the before/after claim, ownership and profile-count snapshot and
   confirm no claim row changed.
3. Run the Supabase security and performance advisors.
4. Run the full `pnpm test:e2e` in a real browser — Playwright could not run in
   the environment this was built in.
5. Visual pass on desktop and on a portrait phone. The panel has been checked
   structurally but **has never been looked at**.

## Rollback

Isolated from claims and houses. Web: revert `inventory-system.js` and its
`town.html` integration. Database: in one transaction, revoke and drop
`add_to_my_inventory(jsonb)`, drop `profiles_inventory_valid`, drop
`followville_inventory_is_valid`, drop the `inventory` column, and re-grant
`update (avatar)` so avatar saving survives. Then recompare the saved claim,
ownership and profile counts. Dropping the column loses only saved fish; it
does not alter a claim, owner, handle, verification record, house or
town-state row.
