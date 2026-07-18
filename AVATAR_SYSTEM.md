# Followville Avatar System v1

Status: released to production on 2026-07-17. The isolated profile migration
was applied and verified before the web release.

## Player experience

- Third-person is the town's default walking camera.
- `V`, the in-town avatar button, the start screen, and the pause menu open the
  full-screen Neighborhood Tailor.
- Custom mode offers 10 skin tones, five age/height proportions, eight face
  silhouettes, six modeled hairstyles, six complete modeled outfits, and two
  hat states.
- Every visible catalog card is captured from the actual selectable 3D model.
  The live preview supports drag rotation plus wheel/pinch zoom.
- Guests persist locally. Signed-in profiles will persist the same validated
  catalog IDs through `profiles.avatar` once the migration is approved/applied.
- Roleplay names are deliberately outside v1.

## Runtime architecture

`avatar-system.js` owns the catalog, validation, lazy GLB loading, assembly,
skin/face/height transforms, shared rig posing, and locomotion. `town.html`
owns the studio UI, preview scene, third-person integration, local storage,
presence refresh, and the owner-only save call.

The default custom avatar loads `core.glb` plus one hair, outfit, and optional
hat. The default initial payload is 512,832 bytes. Component preview JPGs load
only inside their catalog tabs. The former separate complete-character library
was removed on 2026-07-17 so every player uses the same modular animated style.

The avatar files are completely separate from `town.glb`, streamed town
districts, `world_state.json`, and the canonical `neighborhood.blend`. Avatar
export scripts must never open or save the authoritative town scene.

## Source assets and license

The production avatar models come from these CC0 1.0 Quaternius packs:

- Universal Base Characters
- Modular Character Outfits - Fantasy

Source pages and license metadata are retained in
`avatar_assets/avatar_v1/manifest.json`. Licensing is maintainer-facing;
the player UI intentionally uses Followville names only.

Local source packs live outside the repository under
`C:\Users\cadet\.codex\integrations`. The isolated authoring file is
`avatar_assets/source/followville_avatar_library.blend`.

## Rebuild workflow

Use Blender 5.1 from the repository root:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' --background --python scripts\export_avatar_library.py
```

With the local test server running at `http://127.0.0.1:8765`, rebuild visual
cards with the bundled Node runtime:

```powershell
node scripts\capture_avatar_component_thumbnails.mjs
```

The exporter writes a deterministic manifest with byte sizes and SHA-256
hashes.

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

The live constraint still recognizes the retired complete-look IDs for schema
compatibility. The browser normalizer always converts those values to `custom`
before loading or saving, and none of the retired assets or UI remain. The
modular-only correction required no database write.

Rollback is isolated from claims and houses: disable the browser save path,
revoke/drop `update_my_avatar(jsonb)`, drop
`profiles_own_avatar_update`, drop `profiles_avatar_valid`, and drop the
`profiles.avatar` column in one transaction. Restore the exact preflight
`profiles` ACL snapshot rather than blindly granting table-wide update. Then
recompare the saved claim, ownership, and profile counts. Dropping the avatar
column loses only saved avatar selections; it does not alter a claim, owner,
handle, verification record, house, or town-state row.

## Browser verification

The avatar Playwright flows verify modular selections, real component previews,
local persistence, reload persistence, safe legacy-look normalization,
third-person player/camera movement, and clean console behavior. Run:

```powershell
pnpm test:e2e --grep "Avatar Studio"
```

Run the complete `pnpm test:e2e` suite before review or release.

Latest correction verification on 2026-07-17: all three focused avatar
and follow-camera flows plus the full-town fallback passed in Chromium. The
preceding production release passed all 10 browser flows and its modular
manifest checks. See `design-qa.md`.
