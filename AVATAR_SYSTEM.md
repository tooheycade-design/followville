# Followville Avatar System v1

Status: released to production on 2026-07-17. The isolated profile migration
was applied and verified before the web release.

## Player experience

- Third-person is the town's default walking camera. On desktop, right-button
  drag locks/hides the cursor and orbits without screen-edge limits; releasing
  restores the cursor. This path avoids platform-specific held-button state and
  accepts Control-click drag on Mac as a fallback. Wheel/trackpad scrolling
  zooms continuously into true first person: the camera moves to avatar eye
  height, hides the local avatar, locks the cursor, and ordinary mouse movement
  looks around without holding a button. Zooming out restores the cursor. On
  mobile, camera drag works while the other thumb holds the
  joystick, and pinch controls the same third/first-person zoom range. Phone
  gameplay is landscape-only: portrait pauses behind a rotate prompt and the
  interrupted walk resumes automatically after rotation.
- Space on desktop and the dedicated JUMP button on mobile make a short,
  grounded hop. The camera follows its height, a second jump cannot start
  while airborne, and multiplayer movement carries the same vertical offset.
- `V`, the in-town avatar button, the start screen, and the pause menu open the
  full-screen Neighborhood Tailor.
- Characters offers 37 compact animated complete characters grouped into
  Everyday, Town roles, and Adventure. Body offers 10 skin tones and five
  age/height proportions.
- The taller modular face/hair/outfit/hat family is intentionally retired from
  the public UI and runtime. Existing profile JSON retains its stable schema,
  but a legacy `look: custom` value normalizes to `casual_day_m`; no profile or
  claim rows need rewriting.
- Every visible catalog card is captured from the actual selectable 3D model.
  The live preview supports drag rotation plus wheel/pinch zoom.
- Guests persist locally. Signed-in profiles persist the same validated catalog
  IDs through the applied owner-only `profiles.avatar` migration.
- Roleplay names are deliberately outside v1.

## Runtime architecture

`avatar-system.js` owns the catalog, validation, lazy GLB loading,
skin/height transforms, shared rig posing, and locomotion. `town.html`
owns the studio UI, preview scene, third-person integration, local storage,
presence refresh, and the owner-only save call.

The player loads exactly one compressed complete-character GLB. The 37
character GLBs total 2,059,796 bytes and are not part of town startup. Preview
JPGs load only inside the Characters catalog. Retained modular authoring assets
are not reachable from the player loader.

The avatar files are completely separate from `town.glb`, streamed town
districts, `world_state.json`, and the canonical `neighborhood.blend`. Avatar
export scripts must never open or save the authoritative town scene.

## Source assets and license

The production avatar models come from these CC0 1.0 Quaternius packs:

- Universal Base Characters
- Modular Character Outfits - Fantasy
- Ultimate Animated Character Pack

Source pages and license metadata are retained in
`avatar_assets/avatar_v1/manifest.json` and
`avatar_assets/avatar_v1/look-manifest.json`. Licensing is maintainer-facing;
the player UI intentionally uses Followville names only.

Local source packs live outside the repository under
`C:\Users\cadet\.codex\integrations`. The isolated authoring file is
`avatar_assets/source/followville_avatar_library.blend`.

## Rebuild workflow

Use Blender 5.1 from the repository root:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' --background --python scripts\export_avatar_library.py
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' --background --python scripts\export_avatar_look_library.py
```

With the local test server running at `http://127.0.0.1:8765`, rebuild visual
cards with the bundled Node runtime:

```powershell
node scripts\capture_avatar_component_thumbnails.mjs
node scripts\capture_avatar_look_thumbnails.mjs
```

Both exporters write deterministic manifests with byte sizes and SHA-256
hashes. The complete-look exporter bakes each source character's authored idle
stance into a web-safe rig, normalizes it at runtime to a 1.82m baseline, and
does not export animation clips.

## Database rollout

`supabase_migrations/20260717_avatar_system_v1.sql` was applied on 2026-07-17.
It adds only `profiles.avatar`, an exact JSON allowlist constraint, an own-row
RLS update policy, a column-level `UPDATE (avatar)` grant, and the
security-invoker `update_my_avatar(jsonb)` RPC. It does not update houses,
claims, handles, ownership, admin status, world state, population, or geometry.

The production rollout verified:

1. An authenticated user can save their own avatar.
2. Cross-profile avatar updates affect zero rows.
3. Malformed payloads and extra JSON keys are rejected.
4. `anon` cannot execute the RPC or update profiles.
5. Non-avatar profile columns are not client-updatable.
6. Security/performance advisors were run; their remaining notices predate and
   are unrelated to Avatar System v1.
7. The exact claim snapshot remained
   `49e6045d4410c8c4b7432f90c3cabf01`: 30 claims across 29 accounts, with 55
   profiles and 275 houses unchanged.

The saved preflight includes the prior `profiles` ACL, profile-row count, claim
snapshot, and ownership snapshot. The migration intentionally revokes any
table-wide client `UPDATE` privilege on `profiles` before granting only
`UPDATE (avatar)`.

Rollback is isolated from claims and houses: disable the browser save path,
revoke/drop `update_my_avatar(jsonb)`, drop
`profiles_own_avatar_update`, drop `profiles_avatar_valid`, and drop the
`profiles.avatar` column in one transaction. Restore the exact preflight
`profiles` ACL snapshot rather than blindly granting table-wide update. Then
recompare the saved claim, ownership, and profile counts. Dropping the avatar
column loses only saved avatar selections; it does not alter a claim, owner,
handle, verification record, house, or town-state row.

## Browser verification

The focused Playwright flows verify all 37 character choices, absence of public
modular controls/requests, legacy normalization, persistence, continuous camera
follow, right-drag-only orbit, first-person zoom, A/D direction, mobile controls,
the full-GLB fallback, and the bare-town homepage redirect. Run:

```powershell
pnpm test:e2e --grep "animated character library|player camera follows|touch controls|bare legacy|complete-town fallback"
```

Run the complete `pnpm test:e2e` suite before review or release.

Latest local verification on 2026-07-17: all 10 browser flows passed in
Chromium, all 50 manifest-listed GLBs matched their recorded byte sizes and
SHA-256 hashes, and desktop/mobile visual QA passed. See `design-qa.md`.
