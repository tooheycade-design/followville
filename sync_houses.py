#!/usr/bin/env python3
"""Followville: sync world_state.json buildings -> Supabase `houses` table.

Insert-only by design: rows already in the table are NEVER touched, so any
manual edits Cade makes (e.g. flipping `claimable`) survive every sync.

Stdlib only (urllib) — no pip installs needed. Cross-platform (Mac/Linux/
Windows). On Windows the grow pipeline actually uses the PowerShell-native
equivalent inside grow_windows.ps1 (same logic, no Python dependency); this
script is for Mac (grow.sh), manual runs, and backfills.

Config (either real env vars, or a `supabase_sync.env` file next to this
script with KEY=VALUE lines — see CLAIMING_SETUP.md):
  SUPABASE_URL               e.g. https://abcd1234.supabase.co
  SUPABASE_SERVICE_ROLE_KEY  the service-role key (secret! never deploy/push it)

world_state.json is read from $NEIGHBORHOOD_STATE_DIR (or
$NEIGHBORHOOD_REPO_DIR) if set — matching the grow pipeline — else from next
to this script.

Output: last line is HOUSES_SYNC_OK (inserted N) or HOUSES_SYNC_FAILED <why>.
Exit code 0/1 to match.
"""

import json
import os
import sys
import urllib.request
import urllib.error

# Buildings that aren't dwellings — nobody should put a name tag on a pond.
# Everything else (incl. founder houses + milestone buildings, per Cade
# 2026-07-09) is claimable. Flip any row later with:
#   update houses set claimable = true/false where id = <seed>;
NON_CLAIMABLE_TYPES = {"pond", "park", "parkdistrict", "plaza", "streetlight", "car"}

HERE = os.path.dirname(os.path.abspath(__file__))


def load_config():
    cfg = {}
    env_file = os.path.join(HERE, "supabase_sync.env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
    url = os.environ.get("SUPABASE_URL") or cfg.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or cfg.get("SUPABASE_SERVICE_ROLE_KEY")
    return url, key


def state_path():
    d = os.environ.get("NEIGHBORHOOD_STATE_DIR") or os.environ.get("NEIGHBORHOOD_REPO_DIR") or HERE
    return os.path.join(d, "world_state.json")


def rest(url, key, method, path, body=None, prefer=None):
    req = urllib.request.Request(url.rstrip("/") + path, method=method)
    req.add_header("apikey", key)
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", "application/json")
    if prefer:
        req.add_header("Prefer", prefer)
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(req, data=data, timeout=30) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else None


def main():
    url, key = load_config()
    if not url or not key:
        print("HOUSES_SYNC_FAILED missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY "
              "(set env vars or create supabase_sync.env — see CLAIMING_SETUP.md)")
        return 1

    sp = state_path()
    if not os.path.exists(sp):
        print("HOUSES_SYNC_FAILED world_state.json not found at %s" % sp)
        return 1
    with open(sp) as f:
        state = json.load(f)
    buildings = state.get("buildings", [])
    if not buildings:
        print("HOUSES_SYNC_FAILED world_state.json has no buildings (refusing: "
              "looks like the empty-default fallback, not a real town)")
        return 1

    try:
        existing = rest(url, key, "GET", "/rest/v1/houses?select=id&limit=100000")
        existing_ids = {row["id"] for row in existing}
    except urllib.error.HTTPError as e:
        print("HOUSES_SYNC_FAILED fetching existing ids: HTTP %s %s" % (e.code, e.read().decode()[:300]))
        return 1
    except Exception as e:  # noqa: BLE001
        print("HOUSES_SYNC_FAILED fetching existing ids: %s" % e)
        return 1

    rows = []
    for b in buildings:
        if b["seed"] in existing_ids:
            continue
        rows.append({
            "id": b["seed"],
            "gx": b["gx"],
            "gy": b["gy"],
            "building_type": b["type"],
            "day_built": b.get("day", 0),
            "claimable": b["type"] not in NON_CLAIMABLE_TYPES,
        })

    if not rows:
        print("HOUSES_SYNC_OK (inserted 0 — table already up to date, %d buildings)" % len(buildings))
        return 0

    try:
        # ignore-duplicates guards against a concurrent sync racing us
        rest(url, key, "POST", "/rest/v1/houses?on_conflict=id", rows,
             prefer="resolution=ignore-duplicates,return=minimal")
    except urllib.error.HTTPError as e:
        print("HOUSES_SYNC_FAILED insert: HTTP %s %s" % (e.code, e.read().decode()[:300]))
        return 1
    except Exception as e:  # noqa: BLE001
        print("HOUSES_SYNC_FAILED insert: %s" % e)
        return 1

    print("HOUSES_SYNC_OK (inserted %d, %d total buildings in world_state)" % (len(rows), len(buildings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
