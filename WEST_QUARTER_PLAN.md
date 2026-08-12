# Followville chapter four — the West Quarter

Status: a dormant deterministic reserve, added 2026-08-12.

Nothing in this plan changes the canonical Day 41 state, either authoritative
Blend, the current GLBs, the live website, claims, or Supabase. It reserves
1,000 more homes and 22 empty parcels; the source is ready for the guarded
growth that reaches them.

## What it is

One thousand planned houses on a gridded expansion of the quarter Followville
already has — not a second settlement. The addresses exist as data today and
become buildings one follower at a time, exactly like the 1,126 addresses
reserved ahead of them.

- **1,022 addresses** = 1,000 homes + 22 reserved parcels
- **52 streets**, three districts: Harrow Green, Bramble Park, Ember Ridge
- **South arm** y 414..486, x -750..-190 — continues three built streets
- **North arm** y 522..810, x -750..-260 — up the outside of Crown Quarter

## Planning intent

The whole point is that this is the **same quarter carried on**:

- **Southline Avenue, Millrace Street and Kettle Row do not stop at x=-190 any
  more.** They run straight on west to x=-750. Three built streets get longer;
  no new road is invented to replace them.
- The north/south ladder keeps Northgate's 70m module. The avenue ladder keeps
  its 36m module. Blocks are 70 x 36m — the built quarter's own block.
- Kettle Row West ends exactly where Crown Quarter's West Market Street begins.
- From that seam the quarter wraps the city's western and north-western flank.

There is deliberately **no cross street on the seam itself**. One was tried at
x=-190 and does not fit: Southline's own west-end houses stand at x=-173.7, so
a seam street's eastern frontage lands 8m from them and the placer cannot seat
its addresses at all. Nothing is lost — the three avenues already run through.

## Downtown's roads no longer stop

Every one of Crown Quarter's five east/west streets — including both 14m
boulevards — used to end at x=-220 in open meadow. They now run west to x=-260
and meet Forge Avenue, the quarter's eastern edge street, at a junction.

At y=522 this does more than tidy an end: the quarter's Harrow Row is on the
same line, so **Kettle Row and Harrow Row are one continuous road** from
x=-750 through downtown to x=196.

The other four meet the quarter but cannot run **through** it. Crown Quarter's
east/west ladder steps 66m and the West Quarter's steps 36m, so Founders
Boulevard at y=588 lands 6m from Thresher Street at y=594 — closer than either
road is wide; they would merge into one smeared strip. Carrying them through
would mean re-laddering Crown Quarter, which is a bigger decision than this
change. They T into the edge street, which is what an arterial does when it
meets a subdivision's collector.

**A hole this closed:** nothing in the reserve was checking chapter-four
addresses against Crown Quarter's roads at all — a house could have been placed
in the middle of a boulevard. `build_plan()` now clears them. It is gated to
chapter four, because `build_plan` re-solves a whole street at once and
chapters one to three contain **built** addresses whose positions live in
`world_state.json` while their roads come from the plan: re-solving those would
move the road and leave the house standing in it. Measured against Day 41: zero
built plan houses lie within clearance of any Crown Quarter street.

## Density

Lots are **not** uniform. They are tightest against the city and loosen going
west: 4.30m of frontage per address at the seam, 7.40m at the western edge.
Because addresses alternate sides of the street, that is 8.6m between
same-side neighbours at the seam and 14.8m at the edge. The built quarter's own
figure is 9.8m, so the new blocks read as denser than Northgate where they
touch it and as proper suburbs by the time they reach open country.

Every avenue is therefore declared in **three segments** on the cross-street
ladder rather than as one street: `build_plan()` spreads a street's addresses
evenly, so a single street could only ever carry one density. The segments are
collinear and meet end to end, so the built road is continuous.

An earlier table spread the same addresses evenly over half again as much
frontage and left 139 gaps wider than 30m — a grid with missing teeth.

## Where the boundaries come from

They are measured, not chosen.

- **South edge, y=414.** Willow Hills' northernmost houses stand at
  (-241.5, 268.0) on 12.15m ground and (-213.3, 272.2) on 9.08m, and existing
  geometry never moves. A terrace edge further south could not spend its height
  without either cliffing at the seam or lifting the ground under those
  gardens. This is why Northgate Avenue is **not** carried west.
- **East edge of the north arm, x=-260.** Crown Quarter's streets begin at
  x=-220, and this is where they now meet the quarter.
- **North edge, y=810.** Crown Quarter's terrace ends at y=824.
- **West edge, x=-750.** One 70m module further west than first drawn. That is
  not decoration: once Crown Quarter's streets were carried west and chapter
  four had to keep clear of them, measured capacity fell to **998** — two short
  of a thousand, with the solver retrying fifteen times and finding nothing.
  The land west of -680 is empty meadow at 5.3-6.0m, so the module buys the
  frontage back.

## Terrain

The quarter is graded to the same 5.00m datum as Northgate, Southline and
Crown Quarter. The cut is real on the western half: the ridge stands at 24.7m
under Southline Avenue West's middle.

The core runs **x=-766..-300, y=404..826**, feather 110m, west scale 0.55,
east scale 4.00.

Two of those numbers are forced:

- **South, 110m.** The largest Willow Hills allows — from y=404 it dies at
  y=294, twenty-two metres clear of its northernmost houses.
- **East, stopping at x=-300 rather than at the seam.** The obvious core ran
  east to x=-180 so the avenues would meet the built grid on one flat surface,
  and it **moved the built world**: 7.5mm under a standing Northgate house and
  0.203m along Lantern Row, twenty times the 1cm this project holds to. Chapter
  three's own terrace is not quite at full weight out there — its ground sits
  at 5.01-5.18m rather than exactly 5.00 — so lerping it again pulled it down.

  Stopping at -300 leaves the 110m strip between the terrace and the seam on
  natural ground, which turns out to be exactly right: it already runs a smooth
  5.0 to 5.9m, about 1.5% across the strip, so the three avenues ramp gently
  into the built grid with no step and nothing engineered. **A flat surface was
  never the requirement; a continuous one was.**

`downtown_visual_plan.terrain_height` and `town.html`'s
`regionalTerrainHeight` carry the same block and must change together.

## The twenty-two reserved parcels

These are the "leave room for a gas station or a grocery store" spaces. Growth
**steps over them**, the ground stays empty, houses go up around them, and the
building appears only when Cade asks for it.

| Type | Count | Where, and why |
| --- | --- | --- |
| `elementaryschool` | 2 | Orchard Street's northern face |
| `followmart` | 2 | Orchard Street and West Line Road's outer faces |
| `firestation` | 1 | Southline Avenue West, western end |
| `gasstation` | 4 | At through-street junctions |
| `restaurant` | 4 | At through-street junctions |
| `park` | 6 | Spread so no home is far from one |
| `pond` | 3 | Stormwater retention at the low corners |

The three **deep** types need frontage that is both open behind **and** level,
which is a narrower set than it looks. A fire station reaches 41m back from its
own centreline while the next avenue is 36m away, so anywhere inside the grid
is geometrically impossible.

**The fire station took three attempts and is worth reading before moving it.**
It can only front Southline Avenue West from the south, because Millrace Street
is 36m north and its footprint would cross it. So its pad always reaches 31m
south of the terrace, into ground climbing the ridge, and how badly depends on
where along the avenue it stands: near the seam it fell **2.12m**, mid-avenue
**1.88m**, both over the 1.60m cap. At the western end the ridge has dropped to
about 8m and it falls **0.5m**. It sits there and serves the western half.
Anywhere more central is not a preference the ground will grant.

## Growth order

Three districts, filled in this order:

1. **Harrow Green** (302) — the south arm, the one touching Southline, so the
   quarter grows *out of* the existing town on camera.
2. **Bramble Park** (268) — the north arm's inner segments.
3. **Ember Ridge** (452) — the north arm's outer segments.

These addresses are consumed **before** Crown Quarter's towers, because the
allocator takes ordinary house addresses first and only overflows into towers
once the reserve is exhausted. If the towers should rise sooner, that is a
one-line change in `neighborhood_blender.main()` and an owner decision.

## Sizing: the placer is the authority, not arithmetic

Per-street counts in `STREET_SEATS` are **measured against `build_plan()`**,
not estimated. `estimated_seats()` gets the shape right but cannot predict
corner interactions, and sized by arithmetic alone nineteen streets asked for
more than could be placed — Windrow Street 1 by ten. Each street was grown or
trimmed against the placer until it seated exactly what it declares; surplus
was spent nearest the city and shortfalls taken from the far edge, so the
density gradient survives the correction.

Two things that make this non-obvious:

- A crossing street costs about **20m** of frontage, not the 13.5m
  `HOUSE_ROAD_CLEARANCE` implies, because the crossing's own corner address
  eats into this street's frontage too.
- Capacity is **not monotonic** in the requested count. The placer walks
  candidate fractions outward from each address's ideal position, so a street
  that cannot seat N may well seat N at a different total.

## Validation

```bash
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" neighborhood_plan.py
```

That is the one that matters: it places all 2,148 addresses and measures every
one for spacing, frontage, facing, footprint overlap, roads running through
buildings and pad fall.

### What has actually been run

- `west_quarter_plan.py` — 1,022 addresses = 1,000 homes + 22 parcels.
- `metropolitan_plan.py` — 20 towers, 5 east/west streets, 4 ramps.
- `neighborhood_plan.py` — all 2,148 addresses placed and measured, no errors.
- Terrain parity, Blender vs `town.html`, 1,560 samples across the quarter and
  the seam: largest disagreement **0.000000m**.
- Ground under all 1,236 standing buildings, all 1,126 previously reserved
  addresses and every existing plan road: largest change **0.000m**.
- `check_world_geometry.py` on canonical Day 41 — OK. `--self-test` — all nine
  known regressions still caught.
- `check_world_geometry.py` against an **isolated full build-out** (Day 42,
  population 2,740, 2,349 buildings, the whole quarter standing) — OK, 3,404
  roads audited, 16 landmark footprints audited.

One number is worth watching. In the built-out town the worst daylight under a
road deck is **0.090m against a 0.12m limit, at (-190, 486)** — the seam
itself, where Kettle Row West meets the built Kettle Row. It passes, but it is
the tightest point in the town and the first place to look if that check ever
goes red. (On canonical Day 41 the worst is 0.036m elsewhere, because none of
chapter four is built yet; the two figures measure different worlds, and
neither moved when the terrace was pulled back.)
