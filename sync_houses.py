#!/usr/bin/env python3
"""Followville: sync world_state.json buildings -> Supabase `houses` table.

Insert-only by design: rows already in the table are NEVER touched, so any
manual edits Cade makes (e.g. flipping `claimable`) survive every sync. The
guarded exceptions are canonical seed 172's Day 26 school restoration and
seed 524's Day 27 construction-site-to-cinema conversion, and seed 129's Day
44 unclaimed-house-to-arcade conversion. Every correction verifies the exact
old row before changing only civic/commercial metadata.

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
NON_CLAIMABLE_TYPES = {"pond", "park", "parkdistrict", "lanestreet", "plaza", "streetlight", "car",
                       "elementaryschool", "followmart", "coffeetruck", "firestation",
                       "cityhallroad", "cityhall",
                       "civicsquare", "fishingpond", "raftingstation",
                       "weatherstation",
                       "constructionzone", "movietheater", "arcade",
                       "forestreserve",
                       # Chapter three's filling stations and diners. They hold
                       # a growth address each -- "+N followers" still means the
                       # next N addresses appear -- but the whole point is that
                       # they are not homes, so nobody should be able to claim
                       # one and live in it. Every other chapter-three special
                       # was already covered above.
                       "gasstation", "restaurant",
                       # Followville Point Station. It is a power station, not
                       # a home, and without this line the sync would offer a
                       # nuclear reactor as a claimable property.
                       "nuclearplant",
                       "tree", "bush", "rock", "duck"}

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

    state_by_seed = {int(building["seed"]): building for building in buildings}
    restored_school = state_by_seed.get(172)
    if restored_school and restored_school.get("type") == "elementaryschool":
        try:
            rows_172 = rest(
                url, key, "GET",
                "/rest/v1/houses?id=eq.172&select=id,building_type,claimable",
            )
            if len(rows_172) != 1:
                raise RuntimeError("expected exactly one houses row for seed 172")
            current = rows_172[0]
            if current.get("building_type") == "constructionzone" and current.get("claimable") is False:
                rest(
                    url, key, "PATCH", "/rest/v1/houses?id=eq.172",
                    {"building_type": "elementaryschool", "claimable": False},
                    prefer="return=minimal",
                )
                print("HOUSES_CORRECTION_OK seed 172 constructionzone -> elementaryschool")
            elif not (current.get("building_type") == "elementaryschool"
                      and current.get("claimable") is False):
                raise RuntimeError(
                    "seed 172 is not the expected non-claimable school/correctable-zone row"
                )
        except urllib.error.HTTPError as e:
            print("HOUSES_SYNC_FAILED civic correction: HTTP %s %s"
                  % (e.code, e.read().decode()[:300]))
            return 1
        except Exception as e:  # noqa: BLE001
            print("HOUSES_SYNC_FAILED civic correction: %s" % e)
            return 1
    completed_theater = state_by_seed.get(524)
    if completed_theater and completed_theater.get("type") == "movietheater":
        try:
            rows_524 = rest(
                url, key, "GET",
                "/rest/v1/houses?id=eq.524&select=id,building_type,claimable,day_built",
            )
            if len(rows_524) != 1:
                raise RuntimeError("expected exactly one houses row for seed 524")
            current = rows_524[0]
            if (current.get("building_type") == "constructionzone"
                    and current.get("claimable") is False):
                rest(
                    url, key, "PATCH", "/rest/v1/houses?id=eq.524",
                    {"building_type": "movietheater", "claimable": False,
                     "day_built": int(completed_theater.get("day", 27))},
                    prefer="return=minimal",
                )
                print("HOUSES_CORRECTION_OK seed 524 constructionzone -> movietheater")
            elif not (current.get("building_type") == "movietheater"
                      and current.get("claimable") is False):
                raise RuntimeError(
                    "seed 524 is not the expected non-claimable zone/cinema row"
                )
        except urllib.error.HTTPError as e:
            print("HOUSES_SYNC_FAILED theater correction: HTTP %s %s"
                  % (e.code, e.read().decode()[:300]))
            return 1
        except Exception as e:  # noqa: BLE001
            print("HOUSES_SYNC_FAILED theater correction: %s" % e)
            return 1
    completed_arcade = state_by_seed.get(129)
    if completed_arcade and completed_arcade.get("type") == "arcade":
        try:
            rows_129 = rest(
                url, key, "GET",
                "/rest/v1/houses?id=eq.129&select=id,building_type,claimable,day_built",
            )
            if len(rows_129) != 1:
                raise RuntimeError("expected exactly one houses row for seed 129")
            claims_129 = rest(
                url, key, "GET",
                "/rest/v1/claims?house_id=eq.129&select=house_id",
            )
            if claims_129:
                raise RuntimeError("seed 129 has a citizen claim; refusing arcade conversion")
            current = rows_129[0]
            if current.get("building_type") == "house" and current.get("claimable") is True:
                rest(
                    url, key, "PATCH", "/rest/v1/houses?id=eq.129",
                    {"building_type": "arcade", "claimable": False,
                     "day_built": int(completed_arcade.get("day", 44))},
                    prefer="return=minimal",
                )
                print("HOUSES_CORRECTION_OK seed 129 unclaimed house -> arcade")
            elif not (current.get("building_type") == "arcade"
                      and current.get("claimable") is False):
                raise RuntimeError(
                    "seed 129 is not the expected unclaimed house/arcade row"
                )
        except urllib.error.HTTPError as e:
            print("HOUSES_SYNC_FAILED arcade correction: HTTP %s %s"
                  % (e.code, e.read().decode()[:300]))
            return 1
        except Exception as e:  # noqa: BLE001
            print("HOUSES_SYNC_FAILED arcade correction: %s" % e)
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
