"""Pure-data terrain model and audits for the experimental city redesign."""

import math


TERRAIN_BOUNDS = (-520.0, 520.0, -330.0, 520.0)
FACADE_ATTACHMENT_EMBED = 0.01
MIN_VISIBLE_SURFACE_CLEARANCE = 0.05


def mounted_face_center(face, outward, thickness, visible_clearance):
    """Mount a detail across a support plane without sharing its visible face."""
    if outward not in (-1, 1):
        raise ValueError("outward must be -1 or 1")
    if not 0 < visible_clearance < thickness:
        raise ValueError("visible clearance must be between zero and thickness")
    return face + outward * (visible_clearance - thickness / 2)


def mounted_surface_center(face, outward, depth,
                           embed=FACADE_ATTACHMENT_EMBED):
    """Center a facade layer with a small anchor inside its supporting wall."""
    if depth <= embed or embed <= 0:
        raise ValueError("facade depth must exceed its positive embed")
    return mounted_face_center(face, outward, depth, depth - embed)


def visible_face_clearance(face, outward, center, thickness):
    """Signed distance from a support plane to an attachment's visible face."""
    return (center + outward * thickness / 2 - face) * outward


def _smoothstep(edge0, edge1, value):
    if edge0 == edge1:
        return 0.0
    t = max(0.0, min(1.0, (value-edge0)/(edge1-edge0)))
    return t*t*(3.0-2.0*t)


def _gaussian(x, y, cx, cy, sx, sy, height):
    return height*math.exp(-(((x-cx)/sx)**2+((y-cy)/sy)**2)*0.5)


def terrain_height(x, y):
    """Continuous walk surface shared by Blender, roads, houses, and browser.

    Downtown and the established ring district stay level.  The northern and
    north-western suburbs climb through long, driveable grades into rolling
    terrain. Kaleidoscope Crest keeps its authored plateau and is masked out.
    """
    x, y = float(x), float(y)
    north = 5.2*_smoothstep(64.0, 210.0, y)
    west = 3.4*_smoothstep(72.0, 230.0, -x)*_smoothstep(42.0, 145.0, y)
    rolling = (
        _gaussian(x, y, -175, 170, 105, 90, 5.8)
        + _gaussian(x, y, 15, 205, 120, 92, 3.9)
        + _gaussian(x, y, -315, 245, 145, 115, 6.2)
        + _gaussian(x, y, 355, 245, 150, 120, 5.0)
        + _gaussian(x, y, -360, -150, 150, 125, 4.2)
        + _gaussian(x, y, 345, -180, 155, 135, 4.8)
    )
    height = north+west+rolling
    # Keep ordinary streets below roughly a 13% grade while retaining enough
    # relief to read clearly from the skyline and aerial cameras.
    height *= .62
    # Strong distant landforms frame the city in aerial views without forcing
    # steep grades through any current or reserved neighborhood street.
    height += (
        _gaussian(x, y, -445, 330, 105, 120, 24.0)
        + _gaussian(x, y, 455, 345, 115, 125, 26.0)
        + _gaussian(x, y, -455, -245, 120, 110, 21.0)
        + _gaussian(x, y, 455, -255, 125, 115, 23.0)
        + _gaussian(x, y, -235, -155, 88, 82, 17.0)
        + _gaussian(x, y, 250, -175, 92, 86, 15.0)
    )

    # Flat engineered downtown platform with a broad feathered transition.
    # A circular mask clipped the outer grid corners (including the school at
    # -90,-90), allowing meadow terrain to rise through roads and parking lots.
    # Protect the full rectangular Day 15 grid, then start the natural hills
    # beyond it. This keeps every paved corner at one dependable datum.
    downtown_distance = math.hypot((x+3.0)/1.05, (y+5.0)/1.0)
    height *= _smoothstep(88.0, 155.0, downtown_distance)
    downtown_dx = max(0.0, abs(x+3.0)-108.0)
    downtown_dy = max(0.0, abs(y+5.0)-108.0)
    downtown_edge_distance = math.hypot(downtown_dx, downtown_dy)
    # Grade-limit the transition instead of multiplying by a short feather.
    # This preserves the established distant terrain while guaranteeing that
    # the new rectangular platform cannot create a steep lip at its corners.
    height = min(height, downtown_edge_distance * .09)

    # Preserve the established ring district and its connector at grade zero.
    ring_distance = math.hypot((x-169.0)/1.25, (y+3.0)/.85)
    height *= _smoothstep(78.0, 112.0, ring_distance)

    # Kaleidoscope Crest already owns a precise 2.82 m plateau/collider.
    story_distance = math.hypot((x-305.0)/1.15, (y-60.0)/.9)
    height *= _smoothstep(75.0, 112.0, story_distance)
    return max(0.0, height)


def terrain_surface_color(x, y, z=None):
    """Natural continuous terrain color that makes landform readable.

    Low, sheltered ground stays a cooler meadow green. Higher ground becomes
    warmer and slightly drier, while genuinely steep faces expose a muted
    earth/stone tint. Broad deterministic variation prevents a single flat
    green sheet without creating artificial contour rings or tiled noise.
    """
    x, y = float(x), float(y)
    z = terrain_height(x, y) if z is None else max(0.0, float(z))

    # A four-metre derivative is stable at the exported terrain resolution and
    # responds to the real landform rather than to mesh triangulation.
    sample = 4.0
    dzdx = (terrain_height(x+sample, y)-terrain_height(x-sample, y))/(sample*2)
    dzdy = (terrain_height(x, y+sample)-terrain_height(x, y-sample))/(sample*2)
    grade = math.hypot(dzdx, dzdy)

    elevation = _smoothstep(1.2, 18.0, z)
    highland = _smoothstep(7.0, 22.0, z)
    exposed = _smoothstep(.055, .19, grade)
    broad = .5+.5*math.sin(x*.015+math.sin(y*.010)*1.9)
    cross = .5+.5*math.sin(x*.043-y*.037+math.sin((x+y)*.009))
    micro = .5+.5*math.sin(x*.093+y*.071)

    # These deliberately span hue and value, not just "more/less green".
    # Followville's bright daylight transform lifts the final rendered values,
    # so the authored colors need enough separation to survive it.
    lowland = (.292, .505, .222)
    upland = (.402, .455, .215)
    ridge = (.505, .398, .205)
    earth = (.365, .305, .225)

    def blend(a, b, amount):
        return tuple(av+(bv-av)*amount for av, bv in zip(a, b))

    color = blend(lowland, upland, min(1.0, elevation*.78+broad*.12))
    color = blend(color, ridge, highland*(.42+.22*broad))
    color = blend(color, earth, exposed*(.38+.28*highland))

    # Keep close walking views organic but quiet; elevation and slope remain
    # the dominant large-scale cues in drone views.
    value = .955+.055*broad+.030*cross+.018*(micro-.5)
    cool_hollow = (1.0-elevation)*(1.0-exposed)*(.025*(cross-.35))
    return (
        max(0.0, min(1.0, color[0]*value-cool_hollow*.35)),
        max(0.0, min(1.0, color[1]*value+cool_hollow)),
        max(0.0, min(1.0, color[2]*value+cool_hollow*.22)),
        1.0,
    )


def sample_road_points(plan, step=8.0):
    sampled = []
    for index, segment in enumerate(plan.get("roads", [])):
        a, b = segment["a"], segment["b"]
        length = math.hypot(b[0]-a[0], b[1]-a[1])
        count = max(1, int(math.ceil(length/step)))
        for sample in range(count+1):
            t = sample/count
            sampled.append(("future road %d" % index,
                            (a[0]+(b[0]-a[0])*t,
                             a[1]+(b[1]-a[1])*t)))
    return sampled


def audit_terrain(plan, max_road_grade=.16):
    """Ensure every planned road remains driveable on the terrain surface."""
    errors = []
    for index, segment in enumerate(plan.get("roads", [])):
        a, b = segment["a"], segment["b"]
        distance = math.hypot(b[0]-a[0], b[1]-a[1])
        if distance < .001:
            continue
        grade = abs(terrain_height(*b)-terrain_height(*a))/distance
        if grade > max_road_grade:
            errors.append("future road %d terrain grade %.3f exceeds %.3f" %
                          (index, grade, max_road_grade))
    return errors
