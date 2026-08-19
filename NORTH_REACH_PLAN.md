# Followville chapter five — the North Reach

Status: a dormant deterministic reserve, added 2026-08-19.

Nothing in this plan changes the canonical Day 48 state, either authoritative
Blend, the current GLBs, the live website, claims, or Supabase. It reserves
1,000 more homes and 23 empty parcels; the source is ready for the guarded
growth that reaches them.

## Why now

The reserve was **empty**, not nearly empty:

| | |
| --- | --- |
| `world_state.json` | day 48, population 2,360, 2,348 buildings |
| `neighborhood_plan.HOUSE_CAPACITY` | 2,148 |
| planned house addresses | 2,116 |
| **unbuilt house addresses** | **0** |
| overflow already begun | 1 Crown Quarter tower, 11 residents |

Every new follower was becoming a tower resident at a hundred per building.
"Every follower gets a house" had already stopped being true. With this chapter
in the reserve the allocator goes back to houses: the isolated build-out below
starts at plan_id 2149 in Crown Fields and never touches a tower.

## What it is

One thousand planned houses across the top of the city — not a second
settlement. The addresses exist as data today and become buildings one follower
at a time, exactly like the 2,148 addresses reserved ahead of them.

- **1,023 addresses** = 1,000 homes + 23 reserved parcels
- **52 streets**, three neighbourhoods: Crown Fields, Gatehouse Green,
  Kestrel Downs
- **Crown Fields** x -190..160, y 824..1170 — carries downtown's six streets north
- **Gatehouse Green** x -540..-190, y 810..918 — the link, south of the campus
- **Kestrel Downs** x -750..-540, y 810..1134 — the north-west corner

## Planning intent: one ladder, not two

The city's northern edge was already a single 70m module and nobody had
noticed. The West Quarter's cross streets run -750, -680, -610, -540, -470,
-400, -330, -260. Crown Quarter's north/south streets run -190, -120, -50, 20,
90, 160. **And -260 + 70 = -190.** Fourteen lines, one unbroken ladder, 910m
wide.

So this chapter is not joined to the city at a corner or by a single road. Ten
existing streets run straight on through the seam — Crown Quarter's six and
four of the West Quarter's eight — along an 840m edge. The avenue ladder keeps
the West Quarter's 36m module, so blocks are **70 x 36m**: the built quarter's
own block, on both sides of the seam.

Crown Quarter's own east/west ladder steps 66m, but that is a **tower** module
and it stops at Summit Street (y=786). North of y=824 both quarters have ended
and the new blocks are houses, so the residential 36m is the one that
continues.

**Beacon Street (y=882) and Foundry Street (y=918) are each one continuous
910m road** across all three neighbourhoods, declared as three collinear
segments that meet end to end. They are what makes this one district instead of
two grids either side of a gap.

## What chapter four did to its own northern edge

This is the finding that shaped the layout, and it was measured, not assumed.

Orchard Street's north-side houses were placed at y=818.5 by a placer that had
no idea a chapter five would ever continue the streets they sit beside. **Four
of the West Quarter's eight cross streets are therefore closed:**

| Line | What is in the way | Distance |
| --- | --- | --- |
| x=-680 Furrow Avenue | a **built** house at (-677.0, 818.5) | 3.00m |
| x=-610 Sawmill Avenue | a **built** house at (-610.6, 818.5) | 0.59m |
| x=-470 Ridge Avenue | chapter four's school spans x=-475.4..-447.0, and the campus driveway already occupies x=-470 from y=810 to 850 | inside |
| x=-330 Wicker Avenue | chapter four's Follow Mart spans x=-340.2..-306.2 | inside |

Existing geometry never moves, so those lines stay closed. The four that are
clear — -750 (25.9m), -540 (16.5m), -400 (9.2m), -260 (8.4m) — carry the
physical connection. **Furrow and Sawmill are picked back up as interior
streets north of Beacon Street**, where there is nothing to hit; they simply do
not touch the West Quarter any more.

The same survey is why **no chapter-five avenue sits at y=846 west of x=-190**.
Chapter four's Follow Mart reaches y=849.2 and its two schools reach y=843.6,
against a 5.10m `SPECIAL_ROAD_CLEARANCE`. So the first westward avenue is
Beacon Street at y=882. East of x=-190 there is nothing above y=786 at all, so
Crown Fields starts one course lower, at y=846.

## The campus is a fact on the ground, not a plan

`NORTH_CROWN_1000_PLAN.md` is a **review proposal from 2026-08-14 that was
never adopted as written**, and it should not be read as a description of the
world. What actually got built, on 2026-08-15, is the gated North Crown campus:
a 200 x 280m superblock at **x=-470..-270, y=948..1228**, reached by a driveway
that leaves the West Quarter at the Ridge Avenue / Orchard Street junction and
curves north-east to its gate at (-370, 943).

That is squarely inside the land the brief for this chapter described as "flat
open prairie". It is not prairie; it is occupied.

Chapter five does not touch it and does not enclose it. It frames it on three
sides — Gatehouse Green along its southern approach, Kestrel Downs to the west,
Crown Fields 80m to its east — and leaves the pocket around it open. **No
chapter-five address lies inside the keep-out**; the audit reports 0 of 1,023.

The one place the two systems meet is Beacon Street and Foundry Street crossing
the driveway at x=-452 and x=-416, which is a junction. Nothing in
`build_plan()` was looking at that road at all, so a house would simply have
been placed in the middle of it. It now clears it, gated to chapter five for
exactly the reason the Crown Quarter gate is limited to chapter four:
`build_plan()` re-solves a whole street at once, and a built house's position
lives in `world_state.json` while its road comes from the plan, so applying a
new rule to an earlier chapter would move the road and leave the house standing
in the street. The tightest surviving margin is **0.29m**.

## Terrain: nothing to do, and that is the point

**This chapter changes no terrain at all** — not
`downtown_visual_plan.terrain_height`, not `town.html`'s
`regionalTerrainHeight`, no terrace, no shelf. That is not a convenience, it is
the whole risk profile of the chapter. Chapter four's terrace moved Lantern Row
by 0.203m and had to be pulled back 110m from the seam; there is no equivalent
exposure here because nothing is being graded.

It is allowed because the ground is already flat, which was measured before
anything was drawn:

- North of about y=900 the terrain is **constant in y**. Two plateaus —
  **5.332m** west of x=-240 and **3.224m** east of x=-60 — joined by a 180m
  ramp that falls 2.11m: an average of 1.17%, nowhere worse than 1.9%.
- The seam band north of the built quarters falls 1.78m over 80m on its eastern
  half, 2.2%.
- Worst fall across any chapter-five **house** footprint: **0.328m**.
- Worst fall under any of the 23 **civic pads**: **0.523m**, against the 1.60m
  `MAX_SPECIAL_PAD_FALL` cap.

Blender and browser were still checked against each other across the new ground
and the seam, because this ground had never had to render before: 1,570 samples
over x -780..200, y 780..1240, largest disagreement **0.000000m**.

## Density

Lots are **not** uniform. Chapter four's two numbers are kept unchanged — 4.30m
of frontage per address against the city, 7.40m at the far edge, which is 8.6m
and 14.8m between same-side neighbours — but graded along a different axis.
Chapter four ran east/west and graded by x. This chapter fans north and west
from one corner, so the gradient follows the route back **into** the city:

```
reach = (y - 824) + max(0, -190 - x)
```

Crown Fields' seam is at reach 22, its far course at 346, and Kestrel Downs'
far corner at 870 — past the 760m span, so the outermost blocks sit at the full
7.40.

This inverts chapter four's segmentation. There, avenues varied along their
length and had to be cut into three. Here the **avenues run along a constant y,
sit at one reach for their whole length and need no cutting at all**; it is the
cross streets, which span the whole depth of a neighbourhood, that are declared
in segments.

## Where the boundaries come from

- **South edge, y=824 / y=810.** Where Crown Quarter's six north/south streets
  and the West Quarter's cross streets actually stop. The new streets start on
  those exact lines, so the roads are continuous rather than adjacent.
- **East edge, x=160.** Anvil Avenue, the last line of the ladder. The Crown
  Expressway is at x=222 and ends at y=858; the nearest reserved frontage keeps
  53.5m off it.
- **West edge, x=-750.** West Line Road, chapter four's own western edge.
- **Gatehouse Green is two courses deep** because that is exactly what fits
  between chapter four's built back gardens (reaching y=849.2) and the campus
  keep-out (starting y=948). It is thin because the land is thin, not by choice.
- **Kestrel Downs stops at x=-540** and **Crown Fields starts at x=-190**
  because the campus and its 80m/70m setting occupy everything between.
- **North edges, y=1170 and y=1134,** are where the thousandth address lands.
  The prairie continues; the chapter does not need it.

## The twenty-three reserved parcels

These are the "leave room for a gas station or a grocery store" spaces. Growth
**steps over them**, the ground stays empty, houses go up around them, and the
building appears only when Cade asks for it.

| Type | Count | Where, and why |
| --- | --- | --- |
| `elementaryschool` | 2 | Northmoor and Thornfield Streets' northern faces |
| `followmart` | 2 | Anvil Avenue and West Line Road's outer faces |
| `firestation` | 1 | West Market Street North, facing the campus pocket |
| `gasstation` | 5 | At through-street junctions |
| `restaurant` | 4 | At through-street junctions |
| `park` | 6 | Spread so no home is far from one |
| `pond` | 3 | Stormwater retention on the low eastern plateau |

The three **deep** types need frontage that is open behind. A fire station
reaches 41.2m back from its own centreline, a Follow Mart 39.2m and a school
33.6m, while the next avenue is 36m away and `SPECIAL_ROAD_CLEARANCE` is 5.10m
— so anywhere inside the grid is geometrically impossible, not merely tight.
`validate()` re-derives that reach from `TYPE_FOOTPRINT` and fails if a type
ever crosses the line in either direction, so the list cannot rot silently.

The fire station was the one deep site with a real choice to make, and it is
easier here than it was in chapter four. It faces the campus pocket from West
Market Street North's west side, mid-district: open behind, dead level (5.25m
to 5.33m across its 36m footprint, a fall of **0.08m**), central to all three
neighbourhoods, and 39m clear of the campus wall — which is the thing most
likely to need it.

## Growth order

Three neighbourhoods, filled in this order:

1. **Crown Fields** (640 addresses) — carries downtown's own streets north and
   is where the tower overflow is happening, so the chapter grows *out of*
   downtown on camera.
2. **Gatehouse Green** (128) — the link west, past the campus.
3. **Kestrel Downs** (255) — the far north-west corner, last.

## Sizing: the placer is the authority, not arithmetic

Per-street counts in `STREET_SEATS` are **measured against `build_plan()`**,
not estimated. The estimator landed on 1,035 addresses; the placer seated
1,030, refusing four on Beacon Street 1 and two on Hayward Street. Correcting
those left 1,007 homes, and the seven surplus were taken one each off the seven
loosest streets — West Line Road Reach 3 at reach 816 down to West Line Road
Reach 1 at 600 — so **the trim widened the outer edge instead of flattening the
gradient**. A street already carrying a reserved parcel was never trimmed; its
count is sized around a 34m footprint and is not free frontage.

Two things that make this non-obvious, both inherited from chapter four:

- A crossing street costs about **20m** of frontage, not the 13.5m
  `HOUSE_ROAD_CLEARANCE` implies, because the crossing's own corner address
  eats into this street's frontage too.
- Capacity is **not monotonic** in the requested count. The placer walks
  candidate fractions outward from each address's ideal position, and that
  ideal moves when the count changes, so the table was iterated to a fixed
  point rather than solved once.

## Validation

```bash
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" neighborhood_plan.py
```

That is the one that matters: it places all 3,171 addresses and measures every
one for spacing, frontage, facing, footprint overlap, roads running through
buildings and pad fall.

### What has actually been run

- `north_reach_plan.py` — 1,023 addresses = 1,000 homes + 23 parcels, 52
  streets, 3 neighbourhoods. Self-consistency checks pass, including that the
  campus keep-out and driveway still match `world_layout`.
- `neighborhood_plan.py` — all **3,171** addresses placed and measured, no
  errors.
- **Chapters one to four did not move.** The reserve was placed twice, once
  from `HEAD` and once from the working tree, and all **2,148** existing
  addresses compared: identical position, rotation, type and street. Movement
  **0.000m**, exact equality rather than a threshold.
- Terrain parity, Blender vs `town.html`, 1,570 samples across the new ground
  and the seam: largest disagreement **0.000000m**.
- Campus: **0** of 1,023 addresses inside the keep-out, **0** inside the
  driveway clearance, tightest margin 0.29m.
- Civic pad fall: worst **0.523m** against the 1.60m cap.
- `check_world_geometry.py` on canonical Day 48 — OK, 3,407 roads, 16 landmark
  footprints. `--self-test` — all **nine** known regressions still caught.
- `check_town_glb.py` — OK, full GLB and streamed chunks complete and
  state-consistent.
