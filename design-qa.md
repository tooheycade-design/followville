# Avatar System v1 design QA

## Current review target

- Source reference: `C:\Users\cadet\AppData\Local\Temp\codex-clipboard-54caaefc-71be-4e5f-b947-fa87b7c00e55.png`
- Approved player family: the 37 compact animated complete characters in
  `avatar_assets/avatar_v1/look/`, represented by the matching real thumbnails
  in `look-thumb/`.
- The earlier realistic/custom Outfit-tab captures are superseded and must not
  be used as current product evidence.

## Visual assessment

- The desktop 60/40 preview-to-editor split, header baseline, ruled layout,
  serif navigation, warm paper palette, restrained coral selection treatment,
  and dark navy save action now follow the supplied reference closely.
- Every visible catalog card uses a preview captured from the exact selectable
  3D asset. There are no placeholder drawings or text-only stand-ins.
- The avatar is grounded, front-facing, proportionate, and free of the former
  backward-facing/T-pose defects. The neutral studio intentionally replaces
  the reference's rendered tailor room so the actual game model remains the
  visual source of truth.
- The product intentionally offers complete animated characters in the
  Characters tab instead of the taller modular family or separate top/bottom
  assembly.
- At 390 x 844, the preview, horizontally scrollable tabs, three-column visual
  choices, vertical catalog scrolling, and persistent save controls remain
  usable without clipping the active content or producing browser errors.

## Interaction and accessibility assessment

- Characters and Body are the only public tabs. All 37 character cards select
  real models; body color and height update the live 3D preview.
- Preview drag/orbit and wheel/pinch zoom work. In-town desktop orbit requires
  right-drag; scrolling reaches first person. Mobile camera drag remains active
  while the joystick is held, and pinch zoom uses the same camera range.
- Guest choices persist locally across reloads. Signed-in choices persist
  through the verified owner-only profile migration.
- Button and tab roles, labels, selected states, focusable controls, close
  actions, and mobile touch paths are covered by browser tests.
- Player-facing copy does not discuss movement speed or expose asset-source
  licensing details.

## Verification evidence

- Focused Chromium flows passed for the 37-character catalog/persistence,
  camera follow/orbit/zoom/A-D behavior, mobile controls, streamed/full fallback,
  and homepage entry route.
- The complete-character manifest retains byte sizes and SHA-256 hashes for the
  37 selectable GLBs.
- `git diff --check`: passed; only line-ending notices were reported.
- Canonical town data was not changed: Day 16, population 272, 275 buildings,
  existing claims/ownership, `world_state.json`, town geometry, and Blender
  scene remain untouched.

## Severity review

- P0 blockers: none.
- P1 major issues: none.
- Intentional deviation: actual approved compact game-character models replace
  the aspirational reference character/room; clothing is bundled into complete
  characters rather than independent top/bottom/shoe meshes.

final result: passed
