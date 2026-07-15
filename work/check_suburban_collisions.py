"""Read-only OBB collision audit for all normal/ring suburban houses."""

import json
import math
import os
import sys

sys.path.insert(0, ROOT if "ROOT" in globals() else os.path.dirname(os.path.dirname(__file__)))
from neighborhood_plan import PLAN

ROOT = os.path.dirname(os.path.dirname(__file__))
STYLES = [
    (7.9, 5.7), (8.5, 5.4), (7.7, 5.8), (8.3, 5.7), (7.1, 5.7),
    (7.8, 5.8), (7.5, 5.9), (7.2, 5.5), (7.4, 5.8), (7.8, 5.6),
    (7.0, 5.9), (8.4, 5.8), (8.2, 5.9), (6.7, 5.3), (8.6, 5.9),
]
STRUCTURE_SETBACKS = {29: 1.30}
TIGHT_PLAN_IDS = {
    7, 19, 39, 40, 61, 62, 63, 93, 94, 95, 115, 116, 124, 125, 126, 128,
    134, 135, 136, 158, 160, 162, 163, 164, 165, 180, 182, 193, 194, 195,
    196, 197, 205, 206, 207, 208, 211, 212, 255, 256, 257, 258, 259, 260,
    271, 280, 291, 292, 293, 294, 295, 296, 297, 298, 308, 310, 312, 313,
    314, 315, 316, 317, 318, 326, 327, 349, 350,
}


def lot_to_world(gx, gy):
    bx, ix = divmod(gx, 3)
    by, iy = divmod(gy, 3)
    return bx * 36 + ix * 10 + 5, by * 36 + iy * 10 + 5


def rotation(b):
    if b.get("rot") is not None:
        return b["rot"]
    if b.get("face"):
        return {"s": 0.0, "e": math.pi / 2, "n": math.pi, "w": -math.pi / 2}[b["face"]]
    # Tied legacy-grid facings are irrelevant to collision: square 10m lots
    # are non-overlapping. Return the first nearest edge for completeness.
    ix, iy = b["gx"] % 3, b["gy"] % 3
    d = [(iy, 0.0), (2 - iy, math.pi), (2 - ix, math.pi / 2), (ix, -math.pi / 2)]
    return min(d)[1]


def obb(b):
    x, y = ((b["px"], b["py"]) if "px" in b else lot_to_world(b["gx"], b["gy"]))
    style_index = b["seed"] % 15
    w, d = STYLES[style_index]
    scale = 1.0
    if b.get("plan_id"):
        scale = b.get("lot_scale", .55 if b["plan_id"] in TIGHT_PLAN_IDS else .78)
        w *= scale
        d *= scale
    # Include foundation/roof overhang and a small visual breathing margin.
    hx, hy = w / 2 + .36, d / 2 + .36
    a = rotation(b)
    ux, uy = math.cos(a), math.sin(a)
    vx, vy = -math.sin(a), math.cos(a)
    # Local +Y is the rear of these road-facing assets. Founder house #29's
    # structure is shifted rearward while its driveway and walk stay at curb.
    setback = STRUCTURE_SETBACKS.get(b["seed"], 0.0) * scale
    x += vx * setback
    y += vy * setback
    return (x, y, ux, uy, vx, vy, hx, hy)


def overlap(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    axes = ((a[2], a[3]), (a[4], a[5]), (b[2], b[3]), (b[4], b[5]))
    for ax, ay in axes:
        distance = abs(dx * ax + dy * ay)
        ra = a[6] * abs(a[2] * ax + a[3] * ay) + a[7] * abs(a[4] * ax + a[5] * ay)
        rb = b[6] * abs(b[2] * ax + b[3] * ay) + b[7] * abs(b[4] * ax + b[5] * ay)
        if distance >= ra + rb:
            return False
    return True


with open(os.path.join(ROOT, "world_state.json"), encoding="utf-8") as f:
    state = json.load(f)
houses = [b for b in state["buildings"] if b["type"] in ("house", "ringhouse")]
problems = []
for i, first in enumerate(houses):
    for second in houses[i + 1:]:
        # Legacy grid lots are independently guaranteed 10m apart. Audit all
        # exact-position districts, including their relationship to each other.
        if "px" not in first and "px" not in second:
            continue
        if overlap(obb(first), obb(second)):
            problems.append((first["seed"], second["seed"], first.get("plan_id"), second.get("plan_id")))

if problems:
    print("SUBURBAN_COLLISIONS", problems)
else:
    print("SUBURBAN_COLLISIONS_OK", len(houses), "houses")

future = [dict(type="house", px=h["x"], py=h["y"], rot=h["rot"],
               plan_id=h["plan_id"], seed=136 + h["plan_id"])
          for h in PLAN["houses"]]
future_problems = []
for i, first in enumerate(future):
    for second in future[i + 1:]:
        if overlap(obb(first), obb(second)):
            future_problems.append((first["plan_id"], second["plan_id"]))
print("FULL_PLAN_COLLISIONS", len(future_problems), future_problems[:80])
if problems or future_problems:
    raise SystemExit(1)
