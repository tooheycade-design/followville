"""Chapter five: the North Reach, a 1,000-home expansion across the city's top.

This module is pure data.  Importing it creates no Blender objects, edits no
state and builds nothing.  It declares street geometry and address counts;
``neighborhood_plan.build_plan()`` turns them into reserved addresses, and
guarded ``+N`` growth consumes them one follower at a time exactly like the
2,148 addresses reserved ahead of them.

Why this chapter exists
-----------------------
On day 48 the ordinary reserve ran out: 2,116 planned house addresses, 2,116
built, none left.  Population 2,360 against a house capacity of 2,148, and the
overflow had already started -- one Crown Quarter tower holding eleven
residents at a hundred per building.  "Every follower gets a house" stops being
true the moment the reserve empties, and it had.

Where it goes, and why it is the only place left
------------------------------------------------
South and east are full.  The river pins the east flank -- no point on it is
150m from a home, so there is no riverside site to find.  The western ridge
peaks near 31m at (-460, 330) and chapter four deliberately stopped at its
foot.  North is the only direction with room, and the survey says it is
genuinely empty and genuinely flat:

* north of about y=900 the terrain is CONSTANT in y.  Two plateaus -- 5.332m
  west of x=-240, 3.224m east of x=-60 -- joined by a 180m ramp that falls
  2.11m, an average 1.17% and nowhere worse than 1.9%.  The seam band north of
  the built quarters falls 1.78m over 80m on its eastern half, 2.2%.
* every one of those numbers is inside what houses and roads already stand on
  elsewhere in the town, and far inside MAX_SPECIAL_PAD_FALL for a civic pad.

So chapter five needs **no terrace, no shelf and no change to
``terrain_height()`` or town.html's ``regionalTerrainHeight``**.  That is not a
convenience, it is the whole risk profile of the chapter: chapter four's
terrace moved Lantern Row by 0.203m and had to be pulled back 110m from the
seam.  This chapter does not touch the terrain model at all, so nothing that is
already standing can move.

One ladder, not two
-------------------
The city's northern edge is already a single 70m module and nobody had noticed.
The West Quarter's cross streets run -750, -680, -610, -540, -470, -400, -330,
-260; Crown Quarter's north/south streets run -190, -120, -50, 20, 90, 160.
And -260 + 70 = -190.  Fourteen lines, one unbroken ladder, 910m wide.

The avenue ladder is 36m -- the West Quarter's residential module.  Crown
Quarter's own east/west ladder is 66m, but that is a tower module and it stops
at Summit Street (y=786); north of y=824 both quarters have ended and the new
blocks are houses, so the residential 36m is the one that continues.  Blocks
are therefore 70 x 36m, matching the built fabric on both sides of the seam.

What the West Quarter did to its own northern edge
--------------------------------------------------
Only four of the eight West Quarter cross streets can actually be carried
north, and this was measured, not assumed.  Orchard Street's north-side houses
were placed at y=818.5 by a placer that had no idea a chapter five would ever
continue the streets they sit beside, and they are BUILT:

    x=-680  Furrow Avenue      a built house 3.00m off the line
    x=-610  Sawmill Avenue     a built house 0.59m off the line
    x=-470  Ridge Avenue       chapter four's elementary school spans
                               x=-475.4..-447.0, and the campus driveway
                               already occupies x=-470 from y=810 to 850
    x=-330  Wicker Avenue      chapter four's Follow Mart spans
                               x=-340.2..-306.2

Existing geometry never moves, so those four lines are closed.  -750, -540,
-400 and -260 are clear (25.9m, 16.5m, 9.2m and 8.4m to the nearest address)
and carry the physical connection.  Furrow and Sawmill are picked back up as
interior streets north of Beacon Street, where there is nothing to hit -- they
just do not touch the West Quarter any more.

The same survey is why no chapter-five avenue sits at y=846 west of x=-190.
Chapter four's Follow Mart reaches y=849.2 and its two schools reach y=843.6,
and SPECIAL_ROAD_CLEARANCE is 5.10m, so the first westward avenue is Beacon
Street at y=882.  East of x=-190 there is nothing above y=786 at all, so Crown
Fields starts one course lower, at y=846.

The campus is a fact on the ground, not a plan
-----------------------------------------------
The North Crown campus was grown into the live world on 2026-08-15.  It is a
gated 200 x 280m superblock at x=-470..-270, y=948..1228, reached by a driveway
that leaves the West Quarter at the Ridge Avenue / Orchard Street junction and
curves north-east to its gate at (-370, 943).

Chapter five does not touch it and does not enclose it.  It frames it on three
sides -- Gatehouse Green along its southern approach, Kestrel Downs to the
west, Crown Fields 80m to its east -- and leaves the pocket around it open.
The one place the two systems meet is Beacon Street and Foundry Street
crossing the driveway at x=-452 and x=-416, which is a junction; the addresses
either side of it are held off the driveway by the chapter-five-only gate in
``build_plan()``, the same mechanism chapter four uses for Crown Quarter's
roads.

Three neighbourhoods
--------------------
1.  **Crown Fields** -- x=-190..160, y=824..1170.  The main quarter and the
    one that grows first, because it carries downtown's own six streets
    straight north and is where the tower overflow is happening.  350 x 346m.
2.  **Gatehouse Green** -- x=-540..-190, y=810..918.  Two courses deep, which
    is exactly what fits between chapter four's built back gardens and the
    campus keep-out.  It is thin because the land is thin, not by choice, and
    it is what makes Beacon Street and Foundry Street continuous 910m roads
    instead of two unrelated grids.
3.  **Kestrel Downs** -- x=-750..-540, y=810..1134.  The north-west corner,
    210 x 324m, on the 5.33m plateau.

Growth order is Crown Fields, Gatehouse Green, Kestrel Downs, so the chapter
grows out of downtown on camera and reaches the far corner last.

Nothing here moves any existing address.  Chapters one to four are placed
first and cannot be reached by anything declared in this file.
"""

# -- seams -------------------------------------------------------------------
#
# Where the built city stops.  Crown Quarter's six north/south streets end at
# y=824 (metropolitan_plan builds them (x, 486) -> (x, 824)); the West
# Quarter's cross streets end on Orchard Street at y=810.  Chapter five's
# cross streets start on those exact lines, so the roads are continuous rather
# than merely adjacent.
CROWN_SEAM_Y = 824.0
WEST_SEAM_Y = 810.0

# -- the ladder --------------------------------------------------------------
#
# One 70m module across the whole northern edge.  Split by which quarter each
# line comes out of, and by whether chapter four left it open.
CROSS_X_EAST = (-190.0, -120.0, -50.0, 20.0, 90.0, 160.0)      # Crown Quarter
CROSS_X_LINK = (-400.0, -260.0)                                # open, west
CROSS_X_WEST_THROUGH = (-750.0, -540.0)                        # open, far west
CROSS_X_WEST_INTERIOR = (-680.0, -610.0)                       # blocked below
# Closed by chapter four's own built houses and reserved parcels -- kept here
# so the reason is written down next to the lines it removes.
CROSS_X_CLOSED = (-680.0, -610.0, -470.0, -330.0)

# -- the avenue ladder -------------------------------------------------------
#
# 36m, in phase with Orchard Street (y=810) so the new blocks line up with the
# West Quarter's.  846 exists only east of x=-190; see the module docstring.
CROWN_FIELDS_Y = (846.0, 882.0, 918.0, 954.0, 990.0,
                  1026.0, 1062.0, 1098.0, 1134.0, 1170.0)
SHARED_Y = (882.0, 918.0)                   # the two full-width 910m avenues
KESTREL_Y = (882.0, 918.0, 954.0, 990.0, 1026.0, 1062.0, 1098.0, 1134.0)

CROWN_FIELDS_X = (CROSS_X_EAST[0], CROSS_X_EAST[-1])           # -190 .. 160
GATEHOUSE_X = (-540.0, -190.0)
KESTREL_X = (-750.0, -540.0)

CROWN_FIELDS_TOP = CROWN_FIELDS_Y[-1]       # 1170
KESTREL_TOP = KESTREL_Y[-1]                 # 1134
GATEHOUSE_TOP = SHARED_Y[-1]                # 918

DISTRICT_EAST = "Crown Fields"
DISTRICT_LINK = "Gatehouse Green"
DISTRICT_WEST = "Kestrel Downs"
DISTRICT_ORDER = (DISTRICT_EAST, DISTRICT_LINK, DISTRICT_WEST)

# -- the campus, as a keep-out -----------------------------------------------
#
# Mirrors world_layout.LANDMARK_FOOTPRINTS["northcrowncampus"] about its built
# centre (-370, 1088), and world_layout.NORTH_CROWN_CAMPUS_ACCESS.  validate()
# asserts both still agree rather than trusting this copy.
CAMPUS_CENTER = (-370.0, 1088.0)
CAMPUS_FOOTPRINT = (-470.0, -270.0, 948.0, 1228.0)
CAMPUS_ACCESS = ((-470.0, 810.0), (-470.0, 850.0), (-451.0, 884.0),
                 (-416.0, 918.0), (-386.0, 938.0), (-370.0, 943.0))
# Half-width of the driveway.  build_plan() adds the same house and special
# clearances it uses for Crown Quarter's roads on top of this.
CAMPUS_ACCESS_HALF_WIDTH = 3.1

# -- density -----------------------------------------------------------------
#
# Same idea as chapter four and the same two numbers, but graded along a
# different axis.  Chapter four ran east/west and graded by x; this chapter
# fans north and west from one corner of the city, so the gradient follows the
# route back INTO the city:
#
#     reach = (y - 824) + max(0, -190 - x)
#
# -- how far north of downtown's edge an address is, plus how far west of Crown
# Fields it then has to travel.  Crown Fields' seam is at reach 22 and its far
# course at 346; Kestrel Downs' far corner is at 870, past the end of the span,
# so the outermost blocks sit at the full 7.40.  The quarter is tightest where
# it touches downtown and most generous in the north-west corner, which is the
# order a town actually fills in.
#
# The two numbers are chapter four's, unchanged -- the same range of suburban
# density, just measured along a different axis.  They are metres of frontage
# per address; because addresses alternate sides, 4.30 and 7.40 are 8.6m and
# 14.8m between same-side neighbours.  REACH_SPAN is the one number that was
# tuned here, and it was tuned to land the chapter on its thousand homes.
STEP_AT_SEAM = 4.30
STEP_AT_EDGE = 7.40
REACH_SPAN = 760.0
HOUSE_TARGET = 1000

# The estimator build_plan() has to satisfy: an address can only sit in the
# middle 92% of a street, and every crossing blanks frontage around it.
FRONTAGE_WINDOW = 0.92
# 20m, not the 13.5m HOUSE_ROAD_CLEARANCE implies -- the crossing street's own
# corner address takes spacing and footprint clearance out of this street's
# frontage too.  Chapter four measured this the hard way; it is inherited.
JUNCTION_LOSS = 20.0

# Authored ground width plus the 1.50m of visible ground the reserve keeps
# either side of a special.  Mirrors neighborhood_plan.TYPE_FOOTPRINT's x
# extents; validate() asserts the two still agree.
PARCEL_WIDTH = {
    "gasstation": 17.0, "restaurant": 15.4, "pond": 12.4, "park": 24.5,
    "elementaryschool": 28.4, "followmart": 34.0, "firestation": 36.0,
}
PARCEL_MARGIN = 3.0

# How far back from its own centreline each type reaches, so it is obvious
# which types can never sit inside a 36m grid.  setback + half depth:
#     park 29.7  gasstation 20.2  restaurant 19.0  pond 17.6      -> interior
#     elementaryschool 33.6  followmart 39.2  firestation 41.2    -> perimeter
# The next avenue is 36m away and SPECIAL_ROAD_CLEARANCE is 5.10m, so the
# three deep types need open ground behind them and go on an outer face.
DEEP_TYPES = ("elementaryschool", "followmart", "firestation")

# -- names -------------------------------------------------------------------
#
# Crown Fields' cross streets carry Crown Quarter's own names north, because
# they are the same roads.  The West Quarter's carry theirs, with "Reach"
# rather than chapter four's "North"/"South" -- those two suffixes are taken.
CROSS_NAMES = {
    -750.0: "West Line Road Reach", -680.0: "Furrow Avenue Reach",
    -610.0: "Sawmill Avenue Reach", -540.0: "Hollis Avenue Reach",
    -400.0: "Clover Avenue Reach", -260.0: "Forge Avenue Reach",
    -190.0: "West Market Street North", -120.0: "Kiln Avenue North",
    -50.0: "Maple Avenue North", 20.0: "Cedar Avenue North",
    90.0: "Quarry Avenue North", 160.0: "Anvil Avenue North",
}

# The two shared avenues are one road each across all three neighbourhoods,
# numbered 1..3 from the city outward exactly as chapter four numbers its
# segments.  Everything else belongs to a single neighbourhood and is named
# plainly.  Crown Fields and Kestrel Downs use different names above y=918
# because the campus gap means they are NOT the same road at those latitudes.
SHARED_NAMES = {882.0: "Beacon Street", 918.0: "Foundry Street"}
CROWN_FIELDS_NAMES = {
    846.0: "Gateway Row", 954.0: "Tannery Street", 990.0: "Hayward Street",
    1026.0: "Chandler Street", 1062.0: "Fletcher Street",
    1098.0: "Bellows Street", 1134.0: "Quarrier Street",
    1170.0: "Northmoor Street",
}
KESTREL_NAMES = {
    954.0: "Willowbank Street", 990.0: "Peregrine Street",
    1026.0: "Bracken Street", 1062.0: "Gorse Street",
    1098.0: "Heather Street", 1134.0: "Thornfield Street",
}

# Where the cross streets are cut, always on the avenue ladder so no segment
# boundary lands mid-block.  A cross street spans the whole depth of its
# neighbourhood and therefore the whole density gradient; one street can only
# carry one density, so it is declared in segments.  The avenues run along a
# constant y, sit at one reach for their whole length, and need no cutting --
# the mirror image of chapter four, where the avenues were the segmented ones.
CROWN_FIELDS_SEGMENTS = ((824.0, 918.0), (918.0, 1026.0), (1026.0, 1170.0))
KESTREL_THROUGH_SEGMENTS = ((810.0, 918.0), (918.0, 1026.0), (1026.0, 1134.0))
KESTREL_INTERIOR_SEGMENTS = ((882.0, 954.0), (954.0, 1026.0), (1026.0, 1134.0))


# -- the reserved parcels ----------------------------------------------------
#
# Keyed by street name and fraction along it, matching chapters three and four:
# a fraction survives a change in address count, an index does not.
#
#   * The three DEEP types are on perimeter frontage with open ground behind.
#     A fire station reaches 41.2m back from its own centreline and the next
#     avenue is 36m away, so anywhere inside the grid is geometrically
#     impossible, not merely tight.  Every deep site here was checked for pad
#     fall as well as openness; the whole chapter sits on ground that never
#     exceeds 2.2%, so all of them come in far under MAX_SPECIAL_PAD_FALL.
#   * Filling stations and diners sit at junctions with through cross streets,
#     which is where roadside business goes.
#   * Parks are spread so no home is much more than a block and a half away.
#   * The ponds are stormwater retention, at the low corners -- which here is
#     the eastern plateau at 3.22m, the lowest ground in the chapter.
RESERVED_PARCELS = {
    # deep civic sites: open ground behind, level underneath
    #
    # The fire station faces the campus pocket from West Market Street North's
    # west side, mid-district.  That is the one site in the chapter that is
    # open behind, dead level (5.25m to 5.33m across its 36m footprint, a fall
    # of 0.08m) and central enough to reach all three neighbourhoods -- and it
    # is 39m clear of the campus's eastern wall, which is the thing most
    # likely to need it.
    ("West Market Street North", 2): {0.50: "firestation"},
    ("Anvil Avenue North", 2):       {0.45: "followmart"},
    ("West Line Road Reach", 2):     {0.45: "followmart"},
    ("Northmoor Street", None):      {0.42: "elementaryschool"},
    ("Thornfield Street", None):     {0.50: "elementaryschool"},

    # roadside business at the junctions
    ("Gateway Row", None):           {0.30: "gasstation"},
    ("Beacon Street", 1):            {0.62: "restaurant"},
    ("Beacon Street", 2):            {0.40: "gasstation"},
    ("Foundry Street", 1):           {0.35: "gasstation"},
    ("Foundry Street", 3):           {0.55: "restaurant"},
    ("Hayward Street", None):        {0.70: "gasstation"},
    ("Chandler Street", None):       {0.40: "restaurant"},
    ("Peregrine Street", None):      {0.45: "gasstation"},
    ("Gorse Street", None):          {0.50: "restaurant"},

    # neighbourhood parks
    ("Tannery Street", None):        {0.50: "park"},
    ("Fletcher Street", None):       {0.45: "park"},
    ("Quarrier Street", None):       {0.40: "park"},
    ("Willowbank Street", None):     {0.60: "park"},
    ("Bracken Street", None):        {0.35: "park"},
    ("Forge Avenue Reach", None):    {0.30: "park"},

    # stormwater retention at the low corners
    ("Bellows Street", None):        {0.25: "pond"},
    ("Quarry Avenue North", 3):      {0.20: "pond"},
    ("Clover Avenue Reach", None):   {0.50: "pond"},
}


def _step_at(x, y):
    """Metres of frontage per address, graded along the route into the city."""
    reach = (y - CROWN_SEAM_Y) + max(0.0, CROSS_X_EAST[0] - x)
    t = min(1.0, max(0.0, reach / REACH_SPAN))
    return STEP_AT_SEAM + (STEP_AT_EDGE - STEP_AT_SEAM) * t


def estimated_seats(length, crossings, x_mid, y_mid, specials):
    """The first guess at how many addresses a street can seat.

    Reserved parcels are counted at their own width rather than a house's, so
    a street carrying a fire station asks for fewer homes, not the same number
    crammed around it.

    This is how STREET_SEATS below was derived, and it is kept so the shape of
    that table can be re-derived if the density changes -- but it is NOT what
    the reserve uses.  See STREET_SEATS for why.
    """
    step = _step_at(x_mid, y_mid)
    usable = FRONTAGE_WINDOW * length - JUNCTION_LOSS * crossings
    for kind in (specials or {}).values():
        usable -= PARCEL_WIDTH[kind] + PARCEL_MARGIN
    return max(3, int(round(usable / step))) + len(specials or {})


def _street_name(base, part):
    """'Beacon Street 2' for a shared avenue, 'Gateway Row' for a plain one."""
    return base if part is None else "%s %d" % (base, part)


def _entry(district, name, points, specials, crossings):
    # A street missing from STREET_SEATS falls back to the estimate so the
    # table can be re-derived after a layout change; validate() reports it,
    # because an estimated count is a guess and the placer may refuse it.
    x_mid = (points[0][0] + points[-1][0]) / 2.0
    y_mid = (points[0][1] + points[-1][1]) / 2.0
    if name in STREET_SEATS:
        count = STREET_SEATS[name]
    else:
        length = (abs(points[-1][0] - points[0][0])
                  + abs(points[-1][1] - points[0][1]))
        count = estimated_seats(length, crossings, x_mid, y_mid, specials)
    street = dict(district=district, name=name, count=count,
                  culdesac=False, points=points)
    if specials:
        street["specials"] = dict(specials)
    return street


def _avenue_lines_at(x):
    """Every chapter-five avenue latitude that actually has a street at this x."""
    lines = set()
    if CROWN_FIELDS_X[0] <= x <= CROWN_FIELDS_X[1]:
        lines.update(CROWN_FIELDS_Y)
    if GATEHOUSE_X[0] <= x <= GATEHOUSE_X[1]:
        lines.update(SHARED_Y)
    if KESTREL_X[0] <= x <= KESTREL_X[1]:
        lines.update(KESTREL_Y)
    return lines


def _cross_lines_at(y):
    """Every chapter-five ladder line that actually has a street at this y."""
    lines = set()
    for x in CROSS_X_EAST:
        if CROWN_SEAM_Y <= y <= CROWN_FIELDS_TOP:
            lines.add(x)
    for x in CROSS_X_LINK:
        if WEST_SEAM_Y <= y <= GATEHOUSE_TOP:
            lines.add(x)
    for x in CROSS_X_WEST_THROUGH:
        if WEST_SEAM_Y <= y <= KESTREL_TOP:
            lines.add(x)
    for x in CROSS_X_WEST_INTERIOR:
        if KESTREL_INTERIOR_SEGMENTS[0][0] <= y <= KESTREL_TOP:
            lines.add(x)
    return lines


def _between(a, b, lines):
    return sum(1 for line in lines if min(a, b) < line < max(a, b))


def _mid(points):
    return [points[0],
            ((points[0][0] + points[1][0]) / 2.0,
             (points[0][1] + points[1][1]) / 2.0),
            points[1]]


def street_table():
    """Every chapter-five street, ordered so the chapter grows outward."""
    by_district = {name: [] for name in DISTRICT_ORDER}

    # Cross streets first, so the avenues' ends snap onto real junctions.
    for x in CROSS_X_EAST:
        base = CROSS_NAMES[x]
        for index, (y0, y1) in enumerate(CROWN_FIELDS_SEGMENTS):
            name = "%s %d" % (base, index + 1)
            by_district[DISTRICT_EAST].append(_entry(
                DISTRICT_EAST, name, _mid([(x, y0), (x, y1)]),
                RESERVED_PARCELS.get((base, index + 1)),
                _between(y0, y1, _avenue_lines_at(x))))

    for x in CROSS_X_LINK:
        base = CROSS_NAMES[x]
        by_district[DISTRICT_LINK].append(_entry(
            DISTRICT_LINK, base,
            _mid([(x, WEST_SEAM_Y), (x, GATEHOUSE_TOP)]),
            RESERVED_PARCELS.get((base, None)),
            _between(WEST_SEAM_Y, GATEHOUSE_TOP, _avenue_lines_at(x))))

    for x in CROSS_X_WEST_THROUGH + CROSS_X_WEST_INTERIOR:
        base = CROSS_NAMES[x]
        segments = (KESTREL_THROUGH_SEGMENTS if x in CROSS_X_WEST_THROUGH
                    else KESTREL_INTERIOR_SEGMENTS)
        for index, (y0, y1) in enumerate(segments):
            name = "%s %d" % (base, index + 1)
            by_district[DISTRICT_WEST].append(_entry(
                DISTRICT_WEST, name, _mid([(x, y0), (x, y1)]),
                RESERVED_PARCELS.get((base, index + 1)),
                _between(y0, y1, _avenue_lines_at(x))))

    # Avenues.  The two shared ones are declared as three collinear segments
    # that meet end to end, so each is one continuous 910m road on the ground
    # while carrying three densities.
    for y in CROWN_FIELDS_Y:
        if y in SHARED_NAMES:
            base, part = SHARED_NAMES[y], 1
        else:
            base, part = CROWN_FIELDS_NAMES[y], None
        name = _street_name(base, part)
        by_district[DISTRICT_EAST].append(_entry(
            DISTRICT_EAST, name,
            _mid([(CROWN_FIELDS_X[0], y), (CROWN_FIELDS_X[1], y)]),
            RESERVED_PARCELS.get((base, part)),
            _between(CROWN_FIELDS_X[0], CROWN_FIELDS_X[1], _cross_lines_at(y))))

    for y in SHARED_Y:
        base = SHARED_NAMES[y]
        name = _street_name(base, 2)
        by_district[DISTRICT_LINK].append(_entry(
            DISTRICT_LINK, name,
            _mid([(GATEHOUSE_X[0], y), (GATEHOUSE_X[1], y)]),
            RESERVED_PARCELS.get((base, 2)),
            _between(GATEHOUSE_X[0], GATEHOUSE_X[1], _cross_lines_at(y))))

    for y in KESTREL_Y:
        if y in SHARED_NAMES:
            base, part = SHARED_NAMES[y], 3
        else:
            base, part = KESTREL_NAMES[y], None
        name = _street_name(base, part)
        by_district[DISTRICT_WEST].append(_entry(
            DISTRICT_WEST, name,
            _mid([(KESTREL_X[0], y), (KESTREL_X[1], y)]),
            RESERVED_PARCELS.get((base, part)),
            _between(KESTREL_X[0], KESTREL_X[1], _cross_lines_at(y))))

    ordered = []
    for district in DISTRICT_ORDER:
        ordered.extend(by_district[district])
    return tuple(ordered)


# How many addresses each street actually seats -- MEASURED, not estimated.
#
# build_plan() raises if a street cannot seat its declared count, and the
# estimator above cannot predict what happens at a corner, where the crossing
# street's own address, the 7.35m spacing floor and the footprint clearances
# all interact.  Chapter four found nineteen streets over-asked when sized by
# arithmetic alone, one of them by ten.
#
# So every number here was measured against build_plan() itself and baked in.
# Capacity is also not monotonic in the requested count -- the placer walks
# candidate fractions outward from each address's ideal position, and that
# ideal moves when the count changes -- so this was iterated to a fixed point,
# not solved once.
#
# The estimator landed on 1,035 addresses; the placer seated 1,030 of them,
# refusing four on Beacon Street 1 and two on Hayward Street.  Those two were
# corrected to what they actually seat, which left 1,007 homes, and the seven
# surplus were taken one each off the seven loosest streets -- West Line Road
# Reach 3 at reach 816 down to West Line Road Reach 1 at 600 -- so the trim
# widened the outer edge instead of flattening the gradient.  A street already
# carrying a reserved parcel was never trimmed; its count is sized around a
# 34m footprint and is not free frontage.
#
# Change a density constant and this table is stale.  validate() will say so.
STREET_SEATS = {
    "Anvil Avenue North 1": 10, "Anvil Avenue North 2": 6,
    "Anvil Avenue North 3": 13, "Beacon Street 1": 47,
    "Beacon Street 2": 51, "Beacon Street 3": 24, "Bellows Street": 43,
    "Bracken Street": 19, "Cedar Avenue North 1": 10,
    "Cedar Avenue North 2": 12, "Cedar Avenue North 3": 13,
    "Chandler Street": 45, "Clover Avenue Reach": 13, "Fletcher Street": 42,
    "Forge Avenue Reach": 12, "Foundry Street 1": 48,
    "Foundry Street 2": 52, "Foundry Street 3": 22,
    "Furrow Avenue Reach 1": 7, "Furrow Avenue Reach 2": 6,
    "Furrow Avenue Reach 3": 7, "Gateway Row": 52, "Gorse Street": 20,
    "Hayward Street": 44, "Heather Street": 20, "Hollis Avenue Reach 1": 13,
    "Hollis Avenue Reach 2": 9, "Hollis Avenue Reach 3": 8,
    "Kiln Avenue North 1": 10, "Kiln Avenue North 2": 12,
    "Kiln Avenue North 3": 13, "Maple Avenue North 1": 10,
    "Maple Avenue North 2": 12, "Maple Avenue North 3": 13,
    "Northmoor Street": 38, "Peregrine Street": 20, "Quarrier Street": 40,
    "Quarry Avenue North 1": 10, "Quarry Avenue North 2": 12,
    "Quarry Avenue North 3": 12, "Sawmill Avenue Reach 1": 7,
    "Sawmill Avenue Reach 2": 7, "Sawmill Avenue Reach 3": 7,
    "Tannery Street": 45, "Thornfield Street": 17,
    "West Line Road Reach 1": 11, "West Line Road Reach 2": 4,
    "West Line Road Reach 3": 7, "West Market Street North 1": 10,
    "West Market Street North 2": 5, "West Market Street North 3": 13,
    "Willowbank Street": 20,
}


STREETS = street_table()

ADDRESS_COUNT = sum(street["count"] for street in STREETS)
RESERVED_COUNT = sum(len(street.get("specials", ())) for street in STREETS)
HOUSE_COUNT = ADDRESS_COUNT - RESERVED_COUNT


def validate():
    """Everything checkable without placing houses.

    The reserve's own ``neighborhood_plan.validate_plan()`` does the geometric
    work -- spacing, frontage, facing, footprint overlap, roads through
    buildings.  This only checks the declarations are self-consistent, so a
    typo in a street name silently dropping a reserved grocery store is caught
    here rather than discovered as a missing parcel months later.
    """
    errors = []
    if HOUSE_COUNT != HOUSE_TARGET:
        errors.append("the chapter reserves %d homes, not %d -- the density "
                      "constants and STREET_SEATS have drifted apart, and the "
                      "table has to be measured against build_plan() again"
                      % (HOUSE_COUNT, HOUSE_TARGET))

    names = {street["name"] for street in STREETS}
    unknown = set(STREET_SEATS) - names
    for name in sorted(unknown):
        errors.append("STREET_SEATS names '%s', which is not a street" % name)
    if len([s["name"] for s in STREETS]) != len(names):
        errors.append("two streets share a name")

    for base, part in sorted(RESERVED_PARCELS.keys(),
                             key=lambda k: (k[0], str(k[1]))):
        expect = _street_name(base, part)
        if expect not in names:
            errors.append("reserved parcel on '%s' matches no street" % expect)

    # PARCEL_WIDTH is a copy; make it prove it still matches the reserve.
    # Imported lazily because neighborhood_plan imports this module.
    from neighborhood_plan import TYPE_FOOTPRINT, SPECIAL_ROAD_CLEARANCE
    from neighborhood_plan import setback_for
    for kind, width in sorted(PARCEL_WIDTH.items()):
        x0, x1, _, _ = TYPE_FOOTPRINT[kind]
        if abs((x1 - x0) - width) > 0.01:
            errors.append("PARCEL_WIDTH[%s] is %.2f but the reserve builds %.2f"
                          % (kind, width, x1 - x0))

    # DEEP_TYPES must be exactly the types that cannot fit between two avenues
    # 36m apart.  If a footprint is ever retuned this catches the day a type
    # crosses that line in either direction.
    for kind in sorted(PARCEL_WIDTH):
        _, _, y0, y1 = TYPE_FOOTPRINT[kind]
        reach = setback_for(kind) + y1
        fits = reach + SPECIAL_ROAD_CLEARANCE <= 36.0
        if fits and kind in DEEP_TYPES:
            errors.append("%s reaches %.1fm and now fits inside the grid; it "
                          "is still listed as a deep type" % (kind, reach))
        if not fits and kind not in DEEP_TYPES:
            errors.append("%s reaches %.1fm and no longer fits between two "
                          "avenues, but is not a deep type" % (kind, reach))

    # Every deep parcel must be on a street that has open ground behind it.
    deep_streets = set()
    for (base, part), spec in RESERVED_PARCELS.items():
        for kind in spec.values():
            if kind in DEEP_TYPES:
                deep_streets.add(_street_name(base, part))
    perimeter = {"West Market Street North 2", "Anvil Avenue North 2",
                 "West Line Road Reach 2", "Northmoor Street",
                 "Thornfield Street"}
    for name in sorted(deep_streets - perimeter):
        errors.append("deep parcel on '%s', which is not a declared perimeter "
                      "face with open ground behind it" % name)

    if {street["district"] for street in STREETS} != set(DISTRICT_ORDER):
        errors.append("districts do not match the declared growth order")

    # The chapter is joined to the city along a long edge, not at a corner.
    # Crown Quarter's six streets and four of the West Quarter's eight carry
    # straight through the seam; if that ever drops below eight the chapter
    # has become a detached grid joined by a road or two.
    connections = len(CROSS_X_EAST) + len(CROSS_X_LINK) + len(CROSS_X_WEST_THROUGH)
    if connections < 8:
        errors.append("only %d streets cross the seam -- the chapter is no "
                      "longer joined to the city along a long edge" % connections)

    # The campus keep-out is a copy of the built world; make it prove it.
    try:
        from world_layout import (LANDMARK_FOOTPRINTS,
                                  NORTH_CROWN_CAMPUS_ACCESS)
    except ImportError:
        LANDMARK_FOOTPRINTS, NORTH_CROWN_CAMPUS_ACCESS = {}, None
    if "northcrowncampus" in LANDMARK_FOOTPRINTS:
        fx0, fx1, fy0, fy1 = LANDMARK_FOOTPRINTS["northcrowncampus"][:4]
        actual = (CAMPUS_CENTER[0] + fx0, CAMPUS_CENTER[0] + fx1,
                  CAMPUS_CENTER[1] + fy0, CAMPUS_CENTER[1] + fy1)
        if max(abs(a - b) for a, b in zip(actual, CAMPUS_FOOTPRINT)) > 0.01:
            errors.append("CAMPUS_FOOTPRINT is %s but world_layout builds %s"
                          % (CAMPUS_FOOTPRINT, actual))
    if NORTH_CROWN_CAMPUS_ACCESS is not None:
        mine = [tuple(float(v) for v in p) for p in CAMPUS_ACCESS]
        theirs = [tuple(float(v) for v in p) for p in NORTH_CROWN_CAMPUS_ACCESS]
        if mine != theirs:
            errors.append("CAMPUS_ACCESS has drifted from "
                          "world_layout.NORTH_CROWN_CAMPUS_ACCESS")

    # No chapter-five street may enter the campus keep-out at all.  Only the
    # driveway crossings are allowed to come near it, and those are junctions.
    cx0, cx1, cy0, cy1 = CAMPUS_FOOTPRINT
    for street in STREETS:
        for x, y in street["points"]:
            if cx0 <= x <= cx1 and cy0 <= y <= cy1:
                errors.append("'%s' runs inside the campus keep-out at "
                              "(%.0f, %.0f)" % (street["name"], x, y))
                break
    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        raise SystemExit("\n".join(problems))
    print("North Reach: %d addresses = %d homes + %d reserved parcels"
          % (ADDRESS_COUNT, HOUSE_COUNT, RESERVED_COUNT))
    print("%d streets across %d neighbourhoods" % (len(STREETS), len(DISTRICT_ORDER)))
    for district in DISTRICT_ORDER:
        entries = [s for s in STREETS if s["district"] == district]
        print("   %-16s %2d streets  %4d addresses"
              % (district, len(entries), sum(s["count"] for s in entries)))
    kinds = {}
    for street in STREETS:
        for kind in street.get("specials", {}).values():
            kinds[kind] = kinds.get(kind, 0) + 1
    for kind in sorted(kinds):
        print("   %-18s %d" % (kind, kinds[kind]))
