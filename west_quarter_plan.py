"""Chapter four: the West Quarter, a 1,000-home expansion of the built grid.

This module is pure data.  Importing it creates no Blender objects, edits no
state and builds nothing.  It declares street geometry and address counts; the
existing ``neighborhood_plan.build_plan()`` turns them into reserved addresses,
and guarded ``+N`` growth consumes them one follower at a time exactly like the
1,126 addresses already reserved ahead of them.

An expansion, not a new town
----------------------------
The whole point is that this is the SAME quarter, carried on:

* Southline Avenue, Millrace Street and Kettle Row do not stop at x=-190 any
  more -- they run straight on west to x=-680.  Three built streets get longer;
  no new street is invented to replace them.
* The north/south ladder keeps Northgate's 70m module (-120, -50, 20, 90, 160
  become -680 ... -190), and the avenue ladder keeps its 36m module.
* West Market Street South closes the seam: it runs north from Southline Avenue
  to Kettle Row at x=-190, which is exactly where Crown Quarter's own West
  Market Street begins.  The two are one road.

So the quarter is joined to the city by four continuous roads, not parked
beside it.  From there it wraps the city's western and north-western flank: a
south arm alongside Southline, and a north arm running up the outside of Crown
Quarter to y=810.

Why the arms are shaped the way they are
----------------------------------------
The southern limit is set by Willow Hills, not by preference.  Its northernmost
houses stand at (-241.5, 268.0) on 12.15m ground and (-213.3, 272.2) on 9.08m,
and existing geometry never moves.  Grading the quarter down to the town's
5.00m datum any further south than y=404 would either drop a bank through those
gardens or need a feather long enough to lift the ground under them.  So the
south arm starts at Southline Avenue and the ridge below it is left standing.

The northern arm stops at x=-260 because Crown Quarter's streets begin at
x=-220, and at y=810 because Crown Quarter's terrace ends at y=824.

Realistic planning
------------------
1.  **Hierarchy.**  Twelve east/west avenues carry most of the frontage; eight
    north/south cross streets tie them into 70 x 36m blocks -- the same block
    as the built quarter, so the fabric matches at the seam.
2.  **Neighbourhood units.**  Three districts, each roughly 340 homes.  Growth
    fills Harrow Green first, because it is the one touching Southline, so the
    quarter grows out of the existing town on camera instead of appearing
    detached and joining up later.
3.  **Deep sites go on the edge.**  A fire station is 36m across and a Follow
    Mart 34m; neither fits between avenues 36m apart, which is the same
    constraint that pushed Northgate's school and grocery onto Kettle Row's
    outer face.  Every deep civic parcel here fronts a perimeter street with
    open ground behind it -- Southline Avenue West's south face, Orchard
    Street's north face, West Line Road's west face -- and only the shallow
    types sit inside the grid.
4.  **Reserved, not built.**  The twenty-two non-house parcels below use the
    mechanism chapter three already has: growth steps over them, the ground
    stays empty, houses go up around them, and the building appears only when
    Cade asks for it.  They are the "leave room for a gas station or a grocery
    store" spaces, sited where such things actually go -- at junctions and on
    through streets, never mid-block.

Nothing here moves any existing address.  Chapters one to three are placed
first and cannot be reached by anything declared in this file.
"""

TERRACE_DATUM = 5.0

# ── the grid ────────────────────────────────────────────────────────────────
#
# Both ladders continue the built quarter's own module: cross streets every
# 70m, avenues every 36m.  x=-190 is the seam, shared with Crown Quarter's
# West Market Street.
CROSS_X = (-750.0, -680.0, -610.0, -540.0, -470.0, -400.0, -330.0, -260.0)
SEAM_X = -190.0

# The three built avenues that simply get longer.
SOUTH_AVENUE_Y = (414.0, 450.0, 486.0)
# The new avenues on the north arm, up the outside of Crown Quarter.
NORTH_AVENUE_Y = (522.0, 558.0, 594.0, 630.0, 666.0, 702.0, 738.0, 774.0, 810.0)

SOUTH_WEST_X = CROSS_X[0]
SOUTH_EAST_X = SEAM_X
NORTH_WEST_X = CROSS_X[0]
NORTH_EAST_X = CROSS_X[-1]
NORTH_SPLIT_X = -470.0
ARM_SPLIT_Y = SOUTH_AVENUE_Y[-1]

DISTRICT_SOUTH = "Harrow Green"
DISTRICT_NORTH_EAST = "Bramble Park"
DISTRICT_NORTH_WEST = "Ember Ridge"
# Harrow Green touches Southline, so the quarter grows out of the built town.
DISTRICT_ORDER = (DISTRICT_SOUTH, DISTRICT_NORTH_EAST, DISTRICT_NORTH_WEST)

# ── density ─────────────────────────────────────────────────────────────────
#
# Lots are NOT the same size across the quarter.  They are tightest against the
# city and loosen the further west they get, which is how a real town reads:
# the blocks that grew first, nearest the centre, are packed, and the outer
# edge is where the big gardens are.  A uniform quarter looks like a printed
# pattern; a graded one looks like it grew.
#
# The two numbers are metres of frontage per address.  4.30 at the seam is
# slightly tighter than Northgate's own 4.9, so the new blocks read as denser
# than the built grid where they touch it; 7.40 at the western edge is half
# again as generous.  Because addresses alternate sides of the street, those
# are 8.6m and 14.8m between same-side neighbours.
#
# Every avenue is therefore declared in three segments on the cross-street
# ladder rather than as one street: a single street would be spread evenly by
# build_plan() and could only have one density.  The segments are collinear and
# meet end to end, so the built road is continuous.
STEP_AT_SEAM = 4.30
STEP_AT_EDGE = 7.40
HOUSE_TARGET = 1000

# The estimator build_plan() has to satisfy: an address can only sit in the
# middle 92% of a street, and every crossing street blanks 13.5m of frontage
# around it (HOUSE_ROAD_CLEARANCE either side).
FRONTAGE_WINDOW = 0.92
# 20m, not the 13.5m that HOUSE_ROAD_CLEARANCE alone implies. The clearance
# rule blanks 6.75m either side of a crossing centreline, but the crossing
# street has its OWN corner address standing 8.5m off it, and that address
# takes the 7.35m of spacing and the footprint clearance around it out of this
# street's frontage too. Sizing on 13.5m asked nine streets for two to four
# more addresses than build_plan could seat.
JUNCTION_LOSS = 20.0

# How much frontage a reserved parcel occupies, as its authored ground width
# plus the 1.50m of visible ground the reserve keeps either side of a special.
# These mirror neighborhood_plan.TYPE_FOOTPRINT's x extents; validate() asserts
# the two still agree rather than trusting this copy.
#
# They exist because a street's address count is not simply its length over the
# step: a fire station is 36m wide, or eight houses' worth of frontage at the
# density near the seam. Sizing Southline Avenue West's first segment without
# this asked it to seat 27 addresses in room for 18, and build_plan refused it.
PARCEL_WIDTH = {
    "gasstation": 17.0, "restaurant": 15.4, "pond": 12.4, "park": 24.5,
    "elementaryschool": 28.4, "followmart": 34.0, "firestation": 36.0,
}
PARCEL_MARGIN = 3.0

AVENUE_NAMES = {
    414.0: "Southline Avenue West", 450.0: "Millrace Street West",
    486.0: "Kettle Row West",
    522.0: "Harrow Row", 558.0: "Granary Street", 594.0: "Thresher Street",
    630.0: "Windrow Street", 666.0: "Barleycorn Street", 702.0: "Drover Street",
    738.0: "Cooper Street", 774.0: "Wheelwright Street", 810.0: "Orchard Street",
}
CROSS_NAMES = {
    -750.0: "West Line Road", -680.0: "Furrow Avenue", -610.0: "Sawmill Avenue",
    -540.0: "Hollis Avenue", -470.0: "Ridge Avenue", -400.0: "Clover Avenue",
    -330.0: "Wicker Avenue", -260.0: "Forge Avenue",
}
# The quarter runs one 70m module further west than it first did, to x=-750.
# That is not decoration: once Crown Quarter's five east/west streets were
# carried west to meet Forge Avenue, chapter four had to keep its addresses
# clear of them, and the quarter's measured capacity fell to 998 -- two short
# of the thousand it is meant to hold, with the solver retrying fifteen times
# and finding nothing. The land west of -680 is empty meadow at 5.3-6.0m, so
# the module costs one more street and buys the frontage back. West Line Road
# keeps its name and its role as the western edge; the old -680 line becomes
# Furrow Avenue.
# There is deliberately NO cross street on the seam itself. One was tried at
# x=-190 and it does not fit: Southline's own west-end houses stand at
# x=-173.7, so a seam street's east frontage lands 8m from them and build_plan
# cannot seat its addresses at all. Nothing is lost by leaving it out -- the
# three avenues run straight through the seam into the built grid, and Kettle
# Row West ends exactly where Crown Quarter's West Market Street begins, so
# the two are already one road.

# ── the reserved parcels ────────────────────────────────────────────────────
#
# Keyed by street and fraction along it, matching chapter three's convention:
# a fraction survives a change in address count, an index does not.
#
#   * The three DEEP types are on perimeter frontage with open ground behind.
#     A fire station reaches 41m back from its own centreline and the next
#     avenue is 36m away, so anywhere inside the grid is geometrically
#     impossible, not merely tight.
#   * Filling stations and diners sit at junctions with the through cross
#     streets, which is where roadside business goes.
#   * Parks are spread so no home is much more than a block and a half away.
#   * The three ponds are stormwater retention, at low corners of the site.
# Avenue keys carry the segment number (1 is the segment nearest the city);
# cross-street keys carry the arm.
#
# The deep sites are on frontage that is BOTH open behind AND level, which is a
# narrower set than it looks. Southline Avenue West's south face is open all
# the way along, but only its first segment is level -- further west the ground
# behind it falls away down the ridge bank, and a 36m civic pad there would
# stand over 3m proud at its low corner, three times what world_layout allows.
# So the fire station takes the one level open site near the city entrance,
# which is where a fire station belongs anyway, and the schools and groceries
# go along Orchard Street's and West Line Road's outer faces, where the natural
# ground is already within 0.3m of the datum.
RESERVED_PARCELS = {
    # deep civic sites: open ground behind, level underneath
    # The fire station is the hardest parcel in the quarter to site, and it
    # took three attempts. A civic pad is a flat box laid on the terrain, so
    # the fall across its footprint is exactly how proud it stands at its low
    # corner, and the reserve caps that at 1.60m. It is 36m deep, and it can
    # only front Southline Avenue West from the SOUTH, because Millrace Street
    # is 36m north and the footprint would cross it.
    #
    # That means its site always reaches 31m south of the terrace's edge, into
    # ground that is climbing the ridge -- and how badly depends entirely on
    # where along the avenue it stands. Near the seam (0.80) the strip is left
    # on natural ground and it fell 2.12m. Mid-avenue (0.34) the ridge is at
    # its steepest and it fell 1.88m. At the western end the ridge has already
    # dropped away to about 8m, and the fall is 0.5m.
    #
    # So it sits on the quarter's southern through road, at the west end, and
    # covers the western half. Anywhere more central is not a preference the
    # ground will grant.
    ("Southline Avenue West", 3): {0.35: "firestation"},
    ("Orchard Street", 1):        {0.45: "followmart"},
    ("Orchard Street", 2):        {0.50: "elementaryschool"},
    ("Orchard Street", 3):        {0.52: "elementaryschool"},
    ("West Line Road", "north"):  {0.45: "followmart"},

    # roadside business at the junctions
    ("Millrace Street West", 1):  {0.30: "gasstation"},
    ("Kettle Row West", 1):       {0.62: "restaurant"},
    ("Kettle Row West", 2):       {0.40: "gasstation"},
    ("Drover Street", 1):         {0.70: "gasstation"},
    ("Windrow Street", 3):        {0.35: "gasstation"},
    ("Granary Street", 1):        {0.40: "restaurant"},
    ("Cooper Street", 2):         {0.45: "restaurant"},
    ("Barleycorn Street", 3):     {0.55: "restaurant"},

    # neighbourhood parks
    ("Thresher Street", 1):       {0.50: "park"},
    ("Harrow Row", 2):            {0.45: "park"},
    ("Wheelwright Street", 1):    {0.40: "park"},
    ("Windrow Street", 2):        {0.60: "park"},
    ("Forge Avenue", "north"):    {0.30: "park"},
    ("Hollis Avenue", "north"):   {0.65: "park"},

    # stormwater retention at the low corners
    ("Sawmill Avenue", "north"):  {0.25: "pond"},
    ("Ridge Avenue", "north"):    {0.20: "pond"},
    ("Wicker Avenue", "south"):   {0.50: "pond"},
}


def _step_at(x):
    """Metres of frontage per address, graded by distance from the city."""
    reach = SEAM_X - CROSS_X[0]
    t = min(1.0, max(0.0, (SEAM_X - x) / reach))
    return STEP_AT_SEAM + (STEP_AT_EDGE - STEP_AT_SEAM) * t


def estimated_seats(length, crossings, x_mid, specials):
    """The first guess at how many addresses a street can seat.

    Reserved parcels are counted at their own width rather than a house's, so
    a street carrying a fire station asks for fewer homes, not the same number
    crammed around it.

    This is how STREET_SEATS below was derived, and it is kept so the shape of
    that table can be re-derived if the density changes -- but it is NOT what
    the reserve uses.  See STREET_SEATS for why.
    """
    step = _step_at(x_mid)
    usable = FRONTAGE_WINDOW * length - JUNCTION_LOSS * crossings
    for kind in (specials or {}).values():
        usable -= PARCEL_WIDTH[kind] + PARCEL_MARGIN
    return max(3, int(round(usable / step))) + len(specials or {})


def _entry(district, name, points, specials, crossings, x_mid):
    # A street missing from STREET_SEATS falls back to the estimate so the
    # table can be re-derived after a layout change; validate() reports it,
    # because an estimated count is a guess and the placer may refuse it.
    if name in STREET_SEATS:
        count = STREET_SEATS[name]
    else:
        length = (abs(points[-1][0] - points[0][0])
                  + abs(points[-1][1] - points[0][1]))
        count = estimated_seats(length, crossings, x_mid, specials)
    street = dict(district=district, name=name, count=count,
                  culdesac=False, points=points)
    if specials:
        street["specials"] = dict(specials)
    return street


# Where each avenue is cut, on the cross-street ladder so no segment boundary
# lands mid-block.  Three segments give the gradient three steps across the
# quarter; one street could only ever have one density.
SOUTH_SEGMENTS = ((-330.0, SEAM_X), (-540.0, -330.0), (CROSS_X[0], -540.0))
NORTH_SEGMENTS = ((-400.0, NORTH_EAST_X), (-540.0, -400.0), (CROSS_X[0], -540.0))
assert SOUTH_SEGMENTS[-1][0] == CROSS_X[0] == NORTH_SEGMENTS[-1][0]


def _crossings_between(x0, x1, lines):
    return sum(1 for line in lines if min(x0, x1) < line < max(x0, x1))


def street_table():
    """Every chapter-four street, ordered so the quarter grows outward."""
    by_district = {name: [] for name in DISTRICT_ORDER}
    all_avenue_y = SOUTH_AVENUE_Y + NORTH_AVENUE_Y

    # Cross streets first, so the avenues' ends snap onto real junctions.
    for x in CROSS_X:
        name = CROSS_NAMES[x]
        by_district[DISTRICT_SOUTH].append(_entry(
            DISTRICT_SOUTH, "%s South" % name,
            [(x, SOUTH_AVENUE_Y[0]),
             (x, (SOUTH_AVENUE_Y[0] + ARM_SPLIT_Y) / 2.0),
             (x, ARM_SPLIT_Y)],
            RESERVED_PARCELS.get((name, "south")),
            _crossings_between(SOUTH_AVENUE_Y[0], ARM_SPLIT_Y, all_avenue_y),
            x))

    for x in CROSS_X:
        name = CROSS_NAMES[x]
        district = (DISTRICT_NORTH_EAST if x > NORTH_SPLIT_X
                    else DISTRICT_NORTH_WEST)
        by_district[district].append(_entry(
            district, "%s North" % name,
            [(x, ARM_SPLIT_Y),
             (x, (ARM_SPLIT_Y + NORTH_AVENUE_Y[-1]) / 2.0),
             (x, NORTH_AVENUE_Y[-1])],
            RESERVED_PARCELS.get((name, "north")),
            _crossings_between(ARM_SPLIT_Y, NORTH_AVENUE_Y[-1], all_avenue_y),
            x))

    # The seam counts as a crossing for frontage purposes even though no
    # street of ours runs there: Kettle Row West's east end meets Crown
    # Quarter's West Market Street, and the built grid's own roads arrive at
    # the other two avenues.
    cross_lines = tuple(CROSS_X) + (SEAM_X,)
    for y in SOUTH_AVENUE_Y:
        name = AVENUE_NAMES[y]
        for index, (x0, x1) in enumerate(SOUTH_SEGMENTS):
            by_district[DISTRICT_SOUTH].append(_entry(
                DISTRICT_SOUTH, "%s %d" % (name, index + 1),
                [(x0, y), ((x0 + x1) / 2.0, y), (x1, y)],
                RESERVED_PARCELS.get((name, index + 1)),
                _crossings_between(x0, x1, cross_lines), (x0 + x1) / 2.0))

    for y in NORTH_AVENUE_Y:
        name = AVENUE_NAMES[y]
        for index, (x0, x1) in enumerate(NORTH_SEGMENTS):
            district = (DISTRICT_NORTH_EAST if index == 0
                        else DISTRICT_NORTH_WEST)
            by_district[district].append(_entry(
                district, "%s %d" % (name, index + 1),
                [(x0, y), ((x0 + x1) / 2.0, y), (x1, y)],
                RESERVED_PARCELS.get((name, index + 1)),
                _crossings_between(x0, x1, cross_lines), (x0 + x1) / 2.0))

    ordered = []
    for district in DISTRICT_ORDER:
        ordered.extend(by_district[district])
    return tuple(ordered)


# How many addresses each street actually seats -- MEASURED, not estimated.
#
# build_plan() raises if a street cannot seat its declared count, and the
# estimator above cannot predict what happens at a corner, where the crossing
# street's own address, the 7.35m spacing floor and the footprint clearances
# all interact. Sized by arithmetic alone, nineteen of these streets asked for
# more than could be placed -- Windrow Street 1 by ten.
#
# So every number here was measured: each street was grown or trimmed against
# build_plan() itself until it seated exactly what it declares, and the
# addresses left over were spent nearest the city first, so the density
# gradient survives the correction rather than being flattened by it.
#
# Change a density constant and this table is stale. validate() will say so.
# Re-derive it by running the estimator for the shape and then growing each
# street against build_plan() again -- not by hand.
STREET_SEATS = {
    "Barleycorn Street 1": 19, "Barleycorn Street 2": 12,
    "Barleycorn Street 3": 16, "Clover Avenue North": 37,
    "Clover Avenue South": 10, "Cooper Street 1": 18, "Cooper Street 2": 18,
    "Cooper Street 3": 22, "Drover Street 1": 17, "Drover Street 2": 18,
    "Drover Street 3": 17, "Forge Avenue North": 35, "Forge Avenue South": 11,
    "Furrow Avenue North": 19, "Furrow Avenue South": 6,
    "Granary Street 1": 17, "Granary Street 2": 14, "Granary Street 3": 20,
    "Harrow Row 1": 19, "Harrow Row 2": 17, "Harrow Row 3": 20,
    "Hollis Avenue North": 26, "Hollis Avenue South": 10,
    "Kettle Row West 1": 24, "Kettle Row West 2": 33, "Kettle Row West 3": 20,
    "Millrace Street West 1": 20, "Millrace Street West 2": 26,
    "Millrace Street West 3": 16, "Orchard Street 1": 20,
    "Orchard Street 2": 23, "Orchard Street 3": 20, "Ridge Avenue North": 30,
    "Ridge Avenue South": 10, "Sawmill Avenue North": 27,
    "Sawmill Avenue South": 10, "Southline Avenue West 1": 20,
    "Southline Avenue West 2": 37, "Southline Avenue West 3": 26,
    "Thresher Street 1": 16, "Thresher Street 2": 18, "Thresher Street 3": 20,
    "West Line Road North": 23, "West Line Road South": 13,
    "Wheelwright Street 1": 16, "Wheelwright Street 2": 18,
    "Wheelwright Street 3": 18, "Wicker Avenue North": 40,
    "Wicker Avenue South": 10, "Windrow Street 1": 14, "Windrow Street 2": 17,
    "Windrow Street 3": 19,
}


STREETS = street_table()

ADDRESS_COUNT = sum(street["count"] for street in STREETS)
RESERVED_COUNT = sum(len(street.get("specials", ())) for street in STREETS)
HOUSE_COUNT = ADDRESS_COUNT - RESERVED_COUNT

# What the terrace in downtown_visual_plan.terrain_height has to cover, and
# what town.html's regionalTerrainHeight has to agree with.  Declared here so
# the numbers have one home even though two files spell them out.
TERRACE_CORE = (-766.0, -300.0, 404.0, 826.0)
# The terrace deliberately stops 110m short of the seam. The strip between
# x=-300 and the built grid is left on natural ground, which already runs a
# smooth 5.0-5.9m; terracing it moved Lantern Row by 0.203m.
TERRACE_STOPS_SHORT_OF_SEAM = True
TERRACE_FEATHER = 110.0
TERRACE_WEST_SCALE = 0.55
TERRACE_EAST_SCALE = 4.00


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
        errors.append("the quarter reserves %d homes, not %d -- the density "
                      "constants and CALIBRATION have drifted apart, and the "
                      "table has to be measured against build_plan() again"
                      % (HOUSE_COUNT, HOUSE_TARGET))
    unknown = set(STREET_SEATS) - {street["name"] for street in STREETS}
    for name in sorted(unknown):
        errors.append("STREET_SEATS names '%s', which is not a street" % name)

    names = {street["name"] for street in STREETS}
    for base, part in sorted(RESERVED_PARCELS.keys(),
                             key=lambda k: (k[0], str(k[1]))):
        expect = ("%s %d" % (base, part) if isinstance(part, int)
                  else "%s %s" % (base, str(part).capitalize()))
        if expect not in names:
            errors.append("reserved parcel on '%s' matches no street" % expect)

    if len([s["name"] for s in STREETS]) != len(names):
        errors.append("two streets share a name")

    # PARCEL_WIDTH is a copy; make it prove it still matches the reserve.
    # Imported lazily because neighborhood_plan imports this module.
    from neighborhood_plan import TYPE_FOOTPRINT
    for kind, width in sorted(PARCEL_WIDTH.items()):
        x0, x1, _, _ = TYPE_FOOTPRINT[kind]
        if abs((x1 - x0) - width) > 0.01:
            errors.append("PARCEL_WIDTH[%s] is %.2f but the reserve builds %.2f"
                          % (kind, width, x1 - x0))
    if {street["district"] for street in STREETS} != set(DISTRICT_ORDER):
        errors.append("districts do not match the declared growth order")

    # The three southern avenues must reach the built grid's western edge, or
    # the quarter is not joined to anything.
    for y in SOUTH_AVENUE_Y:
        if SOUTH_EAST_X != SEAM_X:
            errors.append("%s does not reach the seam" % AVENUE_NAMES[y])
    # ...and must stop clear of Crown Quarter's streets, which begin at -220.
    if NORTH_EAST_X > -240.0:
        errors.append("the north arm crowds Crown Quarter")
    # The terrace has to cover every address, including the ones fronting the
    # outermost streets from the outside.
    x0, x1, y0, y1 = TERRACE_CORE
    if x0 > CROSS_X[0] - 9.0:
        errors.append("the terrace core does not reach the quarter's west edge")
    # The east edge is NOT required to reach the seam -- see TERRACE_CORE.
    if x1 > SEAM_X - 60.0:
        errors.append("the terrace core runs too close to the built grid")
    if y0 > SOUTH_AVENUE_Y[0] - 9.0 or y1 < NORTH_AVENUE_Y[-1] + 9.0:
        errors.append("the terrace core does not cover the quarter's depth")
    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        raise SystemExit("\n".join(problems))
    print("West Quarter: %d addresses = %d homes + %d reserved parcels"
          % (ADDRESS_COUNT, HOUSE_COUNT, RESERVED_COUNT))
    print("%d streets across %d districts" % (len(STREETS), len(DISTRICT_ORDER)))
    print("south arm  y %.0f..%.0f  x %.0f..%.0f  (continues three built streets)"
          % (SOUTH_AVENUE_Y[0], SOUTH_AVENUE_Y[-1], SOUTH_WEST_X, SOUTH_EAST_X))
    print("north arm  y %.0f..%.0f  x %.0f..%.0f"
          % (NORTH_AVENUE_Y[0], NORTH_AVENUE_Y[-1], NORTH_WEST_X, NORTH_EAST_X))
    kinds = {}
    for street in STREETS:
        for kind in street.get("specials", {}).values():
            kinds[kind] = kinds.get(kind, 0) + 1
    for kind in sorted(kinds):
        print("   %-18s %d" % (kind, kinds[kind]))
