"""How much of the horizon seam does the Day 49 closing frame expose?

Diagnostic only. Renders the closing beat at a handful of candidate altitudes at
quarter resolution and low samples -- a fraction of the cost of one --still --
and measures the dark band at the horizon in each.

**Use this to RANK altitudes, never to quote a number.** At 270x480 a band that
is 7px wide in the delivered 1080x1920 frame is about 1px, and that pixel is a
blend of dark band and bright sky, so it measures far lighter than the real
thing. This pass called the 82m close "31.9% of local sky brightness"; the
delivered full-size frame is 3.0%. The ordering it gives (higher altitude =
wider, darker band) held up; the absolute figures did not, and quoting them
against day 48's full-resolution numbers produced a false all-clear. Measure the
finished frame before believing anything about severity.

The seam itself is settled and is NOT being re-opened: TEAM_LOG 2026-08-18
diagnosed it as the 5.33m step where the authored terrain's perimeter meets the
z=0 background slabs, Cade reviewed the day 48 reel and called it fine, and the
fix is a shared terrain change that needs his say-so. What is in scope here is
purely how hard this camera stares at it. Day 48 closed at 58m and logged a
2-5px hairline at 5-34% of local brightness; day 49's first cut closed at 124m
and produced 10px at 1.8%, which is a black bar rather than a hairline. This
measures where between the two the exposure stops being conspicuous.

Run in the same session as the generator, on a scratch NEIGHBORHOOD_STATE_DIR.
"""

import os

import bpy
import numpy as np

OUT = os.path.join(os.environ.get("TEMP", "."), "day49_close")

# (label, camera position, aim) -- the frame-720 beat, at descending altitudes.
CANDIDATES = (
    ("124m  (first cut)", (70.0, 1105.0, 124.0), (-110.0, 850.0, 16.0)),
    ("100m",              (64.0, 1102.0, 100.0), (-108.0, 862.0, 15.0)),
    ("82m",               (58.0, 1098.0,  82.0), (-106.0, 872.0, 14.0)),
    ("64m",               (52.0, 1094.0,  64.0), (-104.0, 882.0, 13.0)),
)


def measure_band(path):
    """(thickness_px, darkest_fraction_of_local_sky) for the horizon band."""
    img = bpy.data.images.load(path)
    w, h = img.size
    buf = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    lum = buf[:, :, :3].mean(axis=2)
    rows = lum.mean(axis=1)
    bpy.data.images.remove(img)
    darkest = int(np.argmin(rows[: h // 2]))
    ref = rows[max(0, darkest - 10)]
    if ref <= 1e-6:
        return 0, float("nan"), darkest
    band = [y for y in range(max(0, darkest - 20), min(h, darkest + 21))
            if rows[y] < ref * 0.60]
    return len(band), rows[darkest] / ref, darkest


def main():
    scene = bpy.context.scene
    cam = scene.camera
    if cam is None or "Day49NorthReach" not in cam.name:
        raise SystemExit("tune_day49_close: wrong camera %r" % (cam.name if cam else None))
    aim = bpy.data.objects.get("Day49NorthReachAim")

    scene.frame_set(720)
    lens_at_720 = cam.data.lens
    near_at_720 = cam.data.clip_start
    # Drop the animation so the candidates can be posed without the rig
    # snapping back on the next depsgraph evaluation.
    for obj in (cam, aim, cam.data):
        obj.animation_data_clear()
    cam.data.lens = lens_at_720
    cam.data.clip_start = near_at_720

    scene.render.resolution_x = 270
    scene.render.resolution_y = 480
    # The scene is configured for video, which narrows file_format's enum to
    # FFMPEG alone until media_type is switched back to stills first.
    try:
        scene.render.image_settings.media_type = "IMAGE"
    except Exception:
        pass
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.eevee.taa_render_samples = 16
    except Exception:
        pass

    print("\n" + "=" * 72)
    print("DAY 49 CLOSING BEAT -- horizon seam exposure by altitude")
    print("lens %.0fmm, %dx%d diagnostic renders"
          % (lens_at_720, scene.render.resolution_x, scene.render.resolution_y))
    print("=" * 72)
    print("  %-20s %-9s %-10s %s" % ("closing altitude", "band px", "darkest", "horizon row"))
    for label, pos, target in CANDIDATES:
        cam.location = pos
        aim.location = target
        bpy.context.view_layer.update()
        path = os.path.join(OUT, label.split()[0] + ".png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        px, frac, row = measure_band(path)
        # Scale the pixel count to the delivered 1920-tall frame.
        print("  %-20s %-9s %-10s y=%d  (=%.1fpx at 1920)"
              % (label, px, "%.1f%%" % (frac * 100.0), row, px * 4.0))
    print("\n(day 48's accepted closing frame: 2-5px at 5-34%, from 58m)")


main()
