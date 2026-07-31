#!/usr/bin/env python3
"""What can this session actually do? Run me first.

A new agent on this project has no way to know which of its tools work until it
tries one, and the expensive way to find out is halfway through a task. Worse,
the answers differ per tool and per shell: on 2026-07-31 a fresh agent correctly
reported pygltflib missing while it was importable from another shell on the
same machine, because pip could not write into Program Files and had fallen back
to a per-user directory.

So this probes the environment rather than describing it, and prints the exact
command to fix anything missing.

    python check_toolchain.py

Runs on any Python 3. Every check is read-only: nothing is installed, no state
is written, no Blender scene is opened. Exits non-zero only if something needed
just to *inspect* the project is broken.

Capabilities are grouped by what they let you do, because most tasks need only
the first group and there is no point failing a documentation edit because
Chromium is missing.
"""

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
BLENDER_PYTHON = (r"C:\Program Files\Blender Foundation\Blender 5.1\5.1"
                  r"\python\bin\python.exe")
NODE_DIR = r"C:\Program Files\nodejs"
SHARED_BLEND = r"C:\Users\cadet\iCloudDrive\neighborhood\neighborhood.blend"

results = []


def record(group, name, ok, detail, fix=None):
    results.append((group, name, ok, detail, fix))


def run(args, timeout=60):
    """Return (ok, first meaningful line of output)."""
    try:
        done = subprocess.run(args, capture_output=True, text=True,
                              timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        return False, str(error)
    text = (done.stdout or "") + (done.stderr or "")
    line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    return done.returncode == 0, line


# --- inspect: read the project, run the audits -------------------------------

def check_python():
    running = sys.executable
    on_blender = os.path.normcase(running) == os.path.normcase(BLENDER_PYTHON)
    if on_blender:
        record("inspect", "Python", True,
               "Blender's bundled interpreter, %d.%d.%d" % sys.version_info[:3])
        return
    stub = "WindowsApps" in running
    record("inspect", "Python", not stub,
           "running %s%s" % (running, " (Microsoft Store stub)" if stub else ""),
           'use "%s"' % BLENDER_PYTHON if stub else
           'the audits are usually run with "%s"' % BLENDER_PYTHON)


def check_repo_modules():
    sys.path.insert(0, REPO)
    for module in ("downtown_visual_plan", "world_layout", "neighborhood_plan"):
        try:
            __import__(module)
            record("inspect", module, True, "imports")
        except Exception as error:
            record("inspect", module, False, "%s: %s" % (type(error).__name__, error))


def check_state():
    path = os.path.join(REPO, "world_state.json")
    try:
        with open(path) as handle:
            state = json.load(handle)
        record("inspect", "world_state.json", True,
               "day %s, population %s, %d buildings"
               % (state.get("day"), state.get("pop"), len(state["buildings"])))
    except Exception as error:
        record("inspect", "world_state.json", False, str(error))


def check_pygltflib():
    try:
        import pygltflib
        where = os.path.dirname(os.path.dirname(pygltflib.__file__))
        per_user = "AppData" in where
        record("inspect", "pygltflib", True,
               "%s%s" % (where, "  (per-user install: another shell or an "
                                "elevated one may not see it)" if per_user else ""))
    except ImportError:
        record("inspect", "pygltflib", False, "not importable by this Python",
               '& "%s" -m pip install pygltflib' % BLENDER_PYTHON)


def check_git():
    if not shutil.which("git"):
        record("inspect", "git", False, "not on PATH")
        return
    ok, branch = run(["git", "-C", REPO, "branch", "--show-current"])
    _, dirty = run(["git", "-C", REPO, "status", "--porcelain",
                    "--untracked-files=no"])
    _, head = run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"])
    record("inspect", "git", ok,
           "branch %s at %s, %s" % (branch or "?", head or "?",
                                    "uncommitted tracked changes" if dirty
                                    else "clean"))


# --- verify: see the town in a real browser ----------------------------------

def check_node():
    node = os.path.join(NODE_DIR, "node.exe")
    if not os.path.exists(node):
        node = shutil.which("node")
    if not node:
        record("verify", "node", False, "not found",
               'prepend to PATH: $env:PATH = "%s;$env:PATH"' % NODE_DIR)
        return
    ok, version = run([node, "--version"])
    on_path = bool(shutil.which("node"))
    record("verify", "node", ok,
           "%s at %s%s" % (version, node,
                           "" if on_path else
                           "  (NOT on PATH -- Playwright's web server will die "
                           "with \"'node' is not recognized\")"),
           None if on_path else
           '$env:PATH = "%s;$env:PATH"' % NODE_DIR)


def check_playwright():
    cli = os.path.join(REPO, "node_modules", "@playwright", "test", "cli.js")
    node = os.path.join(NODE_DIR, "node.exe")
    if not os.path.exists(cli):
        record("verify", "playwright", False, "node_modules not installed",
               "pnpm install --frozen-lockfile")
        return
    ok, version = run([node, cli, "--version"], timeout=120)
    record("verify", "playwright", ok, version or "no version reported")
    browsers = os.path.join(os.path.expanduser("~"), "AppData", "Local",
                            "ms-playwright")
    chromium = (os.path.isdir(browsers)
                and any(name.startswith("chromium")
                        for name in os.listdir(browsers)))
    record("verify", "chromium", chromium,
           "installed" if chromium else "not installed",
           None if chromium else "pnpm exec playwright install chromium")


def check_preview_port():
    probe = socket.socket()
    probe.settimeout(0.4)
    busy = probe.connect_ex(("127.0.0.1", 8765)) == 0
    probe.close()
    record("verify", "port 8765", True,
           "already serving -- check it is THIS repo before trusting a 404"
           if busy else "free; start with: node tests/serve.mjs")


# --- build: change the world ------------------------------------------------

def check_blender():
    if not os.path.exists(BLENDER):
        record("build", "Blender", False, "not at %s" % BLENDER)
        return
    ok, line = run([BLENDER, "--version"], timeout=120)
    record("build", "Blender", ok, line or "no version reported")


def check_blends():
    repo_blend = os.path.join(REPO, "neighborhood.blend")
    for path in (repo_blend, SHARED_BLEND):
        if not os.path.exists(path):
            record("build", os.path.basename(path), False, "missing at %s" % path)
            return

    def digest(path):
        sha = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                sha.update(block)
        return sha.hexdigest()

    same = digest(repo_blend) == digest(SHARED_BLEND)
    record("build", "Blend copies", same,
           "repo and iCloud match" if same else
           "repo and iCloud DIFFER -- every growth launcher will refuse to run",
           None if same else "reconcile the authoritative scene before growing")


def check_supabase_env():
    path = os.path.join(REPO, "supabase_sync.env")
    present = os.path.exists(path)
    record("build", "supabase_sync.env", True,
           "present -- holds the SERVICE ROLE key, which bypasses row-level "
           "security. Never print, commit or paste its contents."
           if present else
           "absent -- growth still works, the Supabase house sync is skipped")


def main():
    for check in (check_python, check_repo_modules, check_state,
                  check_pygltflib, check_git, check_node, check_playwright,
                  check_preview_port, check_blender, check_blends,
                  check_supabase_env):
        try:
            check()
        except Exception as error:
            record("inspect", check.__name__, False,
                   "check itself failed: %r" % error)

    titles = {
        "inspect": "READ AND AUDIT THE PROJECT  (needed for almost everything)",
        "verify": "SEE IT IN A REAL BROWSER    (needed to verify any visual work)",
        "build": "CHANGE THE WORLD           (needed to grow or re-export)",
    }
    essential_failed = False
    for group in ("inspect", "verify", "build"):
        print("\n%s" % titles[group])
        for entry_group, name, ok, detail, fix in results:
            if entry_group != group:
                continue
            print("  %s  %-18s %s" % ("ok  " if ok else "FAIL", name, detail))
            if fix:
                print("       %s-> %s" % ("" if ok else " ", fix))
            if not ok and group == "inspect":
                essential_failed = True

    print("\nNot probed, because only you can answer it: whether this session "
          "can\ndrive a real browser itself. If you cannot take a screenshot "
          "of a page, say\nso before accepting visual work -- reading the code "
          "is not verification.")
    if essential_failed:
        print("\ncheck_toolchain.py: something needed just to inspect the "
              "project is broken.")
        return 1
    print("\ncheck_toolchain.py: ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
