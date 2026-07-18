#!/usr/bin/env python3
"""Serve Followville's experimental town without production connections.

The local=1 application flag disables Supabase, multiplayer, chat, auth, and
claim writes.  The response policy independently blocks network connections
other than the local files and the pinned Three.js module host.
"""

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from world_layout import walk_surface_manifest as build_walk_surface_manifest


def walk_surface_manifest():
    with open("world_state.json") as handle:
        state = json.load(handle)
    return build_walk_surface_manifest(state)


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
            "script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' https://unpkg.com; "
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
