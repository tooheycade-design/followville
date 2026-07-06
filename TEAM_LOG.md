# Team log — Followville

Plain-English log of who added/changed what, in order. Not a technical changelog
(see WEB_VIEWER_CHANGELOG.md for that) — just enough so Cade and Zach (and whichever
AI is helping each of them) can see what the other did on their turn.

## How to use this
- Whoever finishes a turn (Cade or Zach) adds ONE line before handing off, in this format:
  `YYYY-MM-DD — Name — what changed (one line)`
- If an AI made the change, say so, e.g. "via his Claude" or "via Cade's Claude" —
  that's the whole "tracking" mechanism, no git needed.
- Newest entries at the top.
- Take turns — don't both have neighborhood.blend open / Google Drive syncing changes
  from both sides at the same time. Check Drive's synced before you start your turn.

## Log

2026-07-05 — Cade (via Claude) — added mobile touch controls (joystick + drag-to-look)
  to town.html, fixed the "pancaked houses" export bug, simplified landing page text.
  Set up this shared team-log + Google Drive collaboration workflow for Zach.
2026-07-06 -- Cade (via Claude) -- grew the town to day 5, population 22 (22 houses). Rendered a hero shot of the new houses appearing and a final overhead shot, both copied to the Desktop. Caught and fixed an accidental double-run of the render script that briefly corrupted the state to day 6/pop 28; restored from a day-4 backup before redoing it cleanly. Also corrected a 1-off population/house-count mismatch by hand-editing the pop field to match the 22 built houses.
