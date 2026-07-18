#!/usr/bin/env python3
"""Serve Followville's experimental town without production connections.

The local=1 application flag disables Supabase, multiplayer, chat, auth, and
claim writes.  The response policy independently blocks network connections
other than the local files and the pinned Three.js module host.
"""

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from downtown_visual_plan import terrain_height
from neighborhood_plan import PLAN
from world_layout import DISTRICT_CONNECTORS, transform_point


def walk_surface_manifest():
    with open("world_state.json") as handle:
        state = json.load(handle)
    active = max((building.get("plan_id", 0) for building in state["buildings"]), default=0)
    segments = []

    def append_road(ax, ay, bx, by, half_width=3.25):
        """Mirror the exporter's two-metre, full-width road elevation deck."""
        import math
        length = math.hypot(bx-ax, by-ay)
        steps = max(1, int(math.ceil(length/2.0)))
        samples = []
        for step in range(steps+1):
            t = step/steps
            x, y = ax+(bx-ax)*t, ay+(by-ay)*t
            deck_height = terrain_height(x, y)
            samples.append((x, y, deck_height))
        for a, b in zip(samples, samples[1:]):
            segments.append([a[0], -a[1], a[2], b[0], -b[1], b[2], half_width])
    active_districts = {building.get("district") for building in state["buildings"]
                        if building.get("plan_id")}
    for district in sorted(active_districts):
        connector = DISTRICT_CONNECTORS.get(district, ())
        for (ax, ay), (bx, by) in zip(connector, connector[1:]):
            append_road(ax, ay, bx, by)
    for segment in PLAN["roads"]:
        if segment["reveal_at"] > active:
            continue
        ax, ay = transform_point(*segment["a"], district=segment.get("district"))
        bx, by = transform_point(*segment["b"], district=segment.get("district"))
        # Browser world uses Three.js z=-Blender-y.
        append_road(ax, ay, bx, by)
    bulbs = []
    for bulb in PLAN["turnarounds"]:
        if bulb["reveal_at"] > active:
            continue
        x, y = transform_point(*bulb["center"], district=bulb.get("district"))
        bulbs.append([x, -y, terrain_height(x, y), 8.35])
    return {"activePlanId": active, "segments": segments, "bulbs": bulbs}


class PreviewHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/local_walk_surfaces.json":
            payload = json.dumps(walk_surface_manifest(), separators=(",", ":")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if parsed.path in ("/", "/town.html"):
            query = parse_qs(parsed.query, keep_blank_values=True)
            if query.get("local") != ["1"]:
                query["local"] = ["1"]
                flat = [(key, value) for key, values in query.items() for value in values]
                target = urlunsplit(("", "", "/town.html", urlencode(flat), parsed.fragment))
                self.send_response(302)
                self.send_header("Location", target)
                self.end_headers()
                return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; media-src 'self' blob:; "
            "connect-src 'self' https://unpkg.com; "
            "worker-src 'self' blob:; font-src 'self' data:"
        )
        super().end_headers()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8876), PreviewHandler)
    print("Offline Followville preview: http://127.0.0.1:8876/town.html?local=1")
    server.serve_forever()
