# Followville Interior System v1

Status: polished local release candidate on `codex/interior-builder-polish` as
of 2026-08-03. The backward-compatible database migration is applied; the web
branch is not pushed or deployed.

## Player experience

- Entering a supported claimed home opens a complete 18m x 14m interior with a
  ceiling, framed windows, baseboards, wood-plank floor, warm practical lights,
  entrance doors, and living, dining/kitchen, bedroom, and bathroom zones.
- A curated 34-piece default makes every unsaved home feel finished. Furniture
  and room walls participate in player and follow-camera collision.
- Only the verified owner sees **Furnish my home**. The six catalog categories
  expose 25 approved low-poly pieces with thumbnails. Owners select a piece,
  place it on a 0.25m floor grid, rotate or delete it, undo changes, restore the
  curated default, cancel, or save. Invalid overlaps and out-of-room placement
  are visibly rejected. A home may contain at most 48 pieces.
- Desktop uses pointer placement; landscape phones use touch placement without
  camera-look stealing the gesture. Normal movement pauses while building.
- Saved rooms are shared, not local decoration: visitors to the same house see
  the owner's current layout through the existing claim Realtime flow.

## Runtime architecture

`interior-system.js` owns the catalog, normalization, architecture, asset
loading, furnishing meshes, collisions, build UI, and edit history. `town.html`
owns the established house-entry transition, active claim selection, camera and
player loop, Supabase call, and Realtime refresh.

The room is a separate browser instance at the existing interior coordinates;
it does not modify `world_state.json`, `town.glb`, any district chunk, or the
authoritative Blend. Models load only after a player enters a house. The 25 GLBs
and their WEBP cards total under 1 MB, are served locally, and are never fetched
from a third-party host at runtime. Materials are cloned per placed item so
selection feedback cannot recolor another instance.

The first-generation primitive room remains in `town.html` only as explicitly
marked rollback reference code. Its initializer is not called, so none of its
meshes or lights are constructed.

## Source assets and license

The furniture is a curated subset of Quaternius's Ultimate House Interior Pack,
released under CC0 1.0. Maintainer-facing source, mirror, retrieval date, and
license links are in `assets/interiors/README.md`. Player-facing catalog names
are Followville names; asset attribution is not shown in the game UI.

To add an item, keep all four allowlists synchronized:

1. Put the local GLB and WEBP card in `assets/interiors/quaternius/`.
2. Add approved dimensions, collision footprint, category, and flags to
   `INTERIOR_CATALOG` in `interior-system.js`.
3. Add its stable ID to `update_my_customization` in `supabase_schema.sql`.
4. Add the same ID to a new migration; never silently rewrite an already
   applied migration.

Do not accept client-provided URLs, arbitrary paths, arbitrary transforms, or
unknown IDs. Visually inspect every item at placement scale and from multiple
angles before publishing it.

## Persistence and security

The optional `claims.customization.interior` array uses this normalized shape:

```json
[{"item":"couch_l","x":-4.5,"z":1.25,"r":1}]
```

`supabase_migrations/20260803_interior_builder_v1.sql` upgrades the existing
owner-only `update_my_customization(bigint,jsonb)` RPC. It checks `auth.uid()`
and house ownership before writing, allows only exact item records, limits the
array to 48 and the whole JSON payload to 8192 bytes, bounds X/Z to the room,
snaps positions to 0.25m, and accepts rotation integers 0-3. `anon` and `PUBLIC`
have no execute grant. An exterior-only save preserves a previously saved
interior. Existing version-1 claims remain valid and need no backfill.

The live migration was first tested inside rolled-back transactions. A valid
layout normalized correctly, an unknown asset ID failed, an exterior-only save
preserved the interior, and permissions remained owner-scoped. The before/after
snapshot stayed 40 claims across 39 accounts with digest
`754ed801b3514af5f546255efc54f53a`; no claim row changed.

## Verification and rollback

Focused Playwright coverage enters a real home, checks the catalog, opens owner
build mode, places and removes an item, and cancels cleanly. The manual visual
pass covers default-room desktop views, the full builder, and landscape-phone
placement. Run `pnpm test:e2e` before publishing changes to entry, collision,
customization, or Realtime behavior.

Web rollback is isolated: revert `interior-system.js` and its `town.html`
integration, then restore the retired initializer if the primitive room is
temporarily required. Database rollback should normally leave the compatible
version-2 RPC in place; older clients continue to work and saved arrays remain
preserved. If an emergency requires disabling interior writes, deploy a new
migration that rejects or ignores the `interior` key while retaining existing
JSON data. Never delete interior values, claim rows, or ownership records.
