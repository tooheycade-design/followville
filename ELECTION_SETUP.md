# Followville — the mayoral election

A 48-hour town-wide vote for mayor, run from the website. Built 2026-08-05
(Windows Claude, Opus 5).

**One sentence:** citizens you've already approved get exactly one final vote
each, the ballot is a list of handles you type in yourself, and everyone
watches a live leaderboard until the polls close.

**There is no new account system.** A "citizen" is exactly a profile with
`verification_status = 'verified'` — the same flag you already set when you
approve someone's Instagram DM code on `admin.html`. Anyone you've approved for
a house can vote; nobody else can even see the ballot. Owning a house is *not*
required.

**Stack:** the same one as everything else. Supabase (Postgres) as the backend,
static pages on Vercel. New files: `supabase_migrations/20260805_election_v1.sql`
(run once), `vote.html` (the public page), plus an Election tab inside
`admin.html`. Nothing in Blender, `world_state.json`, the GLBs or the growth
pipeline is touched — this is a `[WEB]` change end to end.

---

## 1. One-time setup (about two minutes)

1. **Run the migration.** Supabase Dashboard → SQL Editor → paste all of
   `supabase_migrations/20260805_election_v1.sql` → Run. Safe to re-run.
   (It is also mirrored at the bottom of `supabase_schema.sql`, which stays the
   single re-runnable canonical schema — running either one is enough.)
2. **Deploy the site.** Push `vote.html`, `index.html`, `admin.html` and
   `vercel.json` to `main`; Vercel does the rest.

Until step 1 is done the site behaves gracefully: `/vote` says "no election is
running" and the admin Election tab tells you which file to run. Nothing breaks.

## 2. Running an election

Everything happens on the **Election** tab of `admin.html` (log in as an admin
on the live site, or run `admin.bat` locally).

1. **Create it.** The picker starts on `+ new election…`. Set the title and the
   blurb that appears above the ballot, leave *published* unticked for now, and
   press **save**.
2. **Type in the candidates.** Handle is required; display name and a 280-char
   pitch are optional and both show on the ballot. Enter submits, so you can
   type ~30 of them without touching the mouse. Handles are lowercased and
   `@`-stripped for you, and the same handle can't be added twice.
3. **Open the poll.** Press **▶ open the poll for 48 hours now**. That
   publishes the election, sets the opening time to that moment and the closing
   time to exactly 48 hours later. (Or set *opens*/*closes* by hand and tick
   *published* — the button is just the common case.)
4. **Watch it.** Live standings, ballots cast, and turnout against the citizen
   roll are on the same tab, refreshing every 30 seconds.
5. **It ends by itself.** At the closing time voting stops and `/vote` shows the
   winner and the final standings. **close the poll now** ends it early; votes
   already cast are kept and the result stands.

### The ballot freezes when voting starts

The moment the first vote lands, candidates can no longer be added or removed —
the admin page hides those controls and the database refuses them
(`ballot_locked`). Changing the field mid-race would invalidate votes already
cast against the old field. **So get every candidate in before you open the
poll.**

## 3. What voters see

`/vote` (also linked from the homepage as *Vote for mayor*) shows a different
page depending on who is looking:

| Who | What they get |
| --- | --- |
| Signed out | "You need to be a citizen to vote", how to become one, and a link to sign up. Plus the closing time and how many are running — **no names, no counts**. |
| Signed in, no handle set | "One step left" — finish account setup. |
| Pending approval | "Your citizenship is pending" — DM the code to @thefollowville. Re-checks every few seconds, so it flips to the ballot the moment you approve them. |
| Rejected | Told plainly they can't vote. |
| **Citizen, poll not open yet** | The field of candidates, no voting yet, opening time. |
| **Citizen, poll open** | The ballot on the left, live leaderboard on the right. |
| **Citizen, already voted** | Who they voted for, plus the live leaderboard. |
| Anyone, poll closed | The winner and the final standings. |

The ballot is listed **alphabetically** and the leaderboard **by votes**, so
ballot order never tracks who is winning. Selecting a candidate raises a
confirm step that says the vote is permanent before anything is sent.

## 4. The rules, and where they are actually enforced

None of these live in the browser. `vote.html` is a display; deleting it would
not let anyone cheat.

| Rule | Enforced by |
| --- | --- |
| One vote per citizen | `election_votes` PRIMARY KEY `(election_id, user_id)`. Two simultaneous requests cannot both land. |
| A vote is final | No update path exists. `cast_vote()` only INSERTs and no client has UPDATE on the table. |
| Only citizens vote | `cast_vote()` re-reads `verification_status` from `profiles` using `auth.uid()`. |
| Only citizens see the ballot or tally | `election_state()` returns names and counts only to verified callers. The three tables have RLS on with **no** select policy and no grants — there is no direct read path at all. |
| Voting only within the window | `cast_vote()` compares against the server's `now()`. The countdown on the page is display only; a wrong or edited client clock changes nothing. |
| Candidates may vote, including for themselves | Candidates are handles on a ballot, voters are accounts. Nothing links them, so nothing blocks it. |
| Only admins run the election | Every `admin_*` function re-checks `profiles.is_admin` (or the service role) inside the function body. |
| The ballot freezes once voting starts | `admin_candidate_add` / `admin_candidate_remove` raise `ballot_locked`. |

Voter privacy: the tally is public to citizens, but **who voted for whom is
not**. `election_state()` returns only your own `my_vote`, and
`admin_election_report()` returns per-candidate totals — there is deliberately
no function, for admins or anyone else, that maps a voter to their choice.

## 5. Live-count refresh

The leaderboard polls `election_state()` every 5 seconds while the tab is
visible, and pauses when it is hidden. It deliberately does **not** use Realtime
on `election_votes`: Realtime pushes whole rows, and those rows contain
`user_id`, so subscribing would risk leaking who voted for whom. Polling a
function that returns only aggregates cannot.

## 6. Testing

`tests/followville.spec.mjs` covers the signed-out paths, which are the ones
that matter publicly — that `/vote` never renders a candidate or a standing to
a non-citizen. The signed-in paths need a real Supabase account; check by hand:

- [ ] a pending account sees "pending", not the ballot
- [ ] approving that account (Accounts tab) flips `/vote` to the ballot within ~5s
- [ ] casting a vote shows the confirm step, then the "your vote is in" banner
- [ ] reloading does not offer a second vote, and the count went up by exactly 1
- [ ] a second account voting for someone else moves both bars
- [ ] `close the poll now` reveals the winner
- [ ] a signed-out browser on `/vote` still sees only the citizen gate

## 7. Rollback

The rollback block at the top of `supabase_migrations/20260805_election_v1.sql`
drops the three tables and eight functions. **It destroys every vote** — export
`election_votes` first if the result still matters. It touches nothing else:
no profile, claim, house, chat or session row is involved. On the web side,
deleting `vote.html` and the `#voteBtn` card in `index.html` removes the
feature with no other effect.
