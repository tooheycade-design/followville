# Followville Stories — the second content format

Written 2026-08-10 from Cade's direction. This is an **addition**, not a
replacement: the Daily Growth video series continues exactly as it is, and
nothing in `CLAUDE.md`'s growth, export, audit or deploy workflow changes.

**One sentence:** short episodic videos about *events* inside the persistent
Followville world, shot in the real Blender city, told entirely through the
environment because no people are ever shown.

Daily Growth documents the population. Stories document the culture. The
project goes from "a city where every follower gets a house" to "a city where
every follower gets a house — and then things actually happen in that city."

Stories do **not** need to be daily. They ship whenever there is time and a
strong enough concept.

---

## 1. What a Story has to do

Every Story should hit several of these, not necessarily all:

1. **Entertain a non-follower.** It must work as standalone short-form. Someone
   who has never heard of Followville should still see something funny,
   strange, dramatic or surprising. The story earns the attention, not the
   branding.
2. **Attract new followers.** The viewer becomes curious and understands that
   following makes them part of a growing world.
3. **Bring existing citizens back.** "What's happening in Followville today?
   What house is going to be featured? Could something happen to *my*
   property?" That is a second reason to watch beyond the population update.
4. **Drive registration and house claiming.** Claiming has to mean something.
   Registered citizens with claimed homes can have their property selected for
   a future Story. The thought to produce is *"wait — that could be my house."*
5. **Create lore.** Recurring locations, businesses, organizations, city
   history, mysteries, running jokes, recognizable properties. The world should
   accumulate history.
6. **Create monetization openings** — custom properties, business builds,
   property reveals, sponsored locations, sponsored Stories, music
   integrations. Native to the world, never an interruption.

---

## 2. Absolute rule: no people

**Never create visible humans, citizens, humanoid NPCs or human characters for
a produced Story video.** This is a core visual rule of the format, not a
technical limitation to route around.

The videos show **the world**, not the people living in it. Real players may of
course appear as avatars when they are actually using the multiplayer website —
that is `AVATAR_SYSTEM.md`'s territory and is unaffected. What is banned is
modelling people into the rendered videos.

**Therefore the environment tells the story.** The vocabulary is: buildings,
houses, vehicles, trucks, doors, gates, packages, signs, lights, props,
weather, particles, smoke, alarms, construction, before/after states, camera
movement, and suggested sound.

The worked example, which is the house style:

> **Don't:** animate a postal worker walking out of a truck, carrying a
> package, and setting it down at a door.
>
> **Do:** postal truck backs up to the house — CUT — package is now sitting
> outside — CUT — package begins shaking — CUT — package bursts open — CUT —
> house and street are buried in rubber ducks.

The viewer understands what happened without seeing a person. That gap is the
style.

---

## 3. Blender is still the source of truth

Stories are produced inside the **actual Followville Blender world**. This is
not a request to generate generic AI video.

```text
IDEA → STORYBOARD → REAL BLENDER WORLD → BUILD ASSETS → ANIMATE →
RENDER SHOTS → HUMAN EDIT → FINAL REEL
```

AI's job is to *direct and produce* the Blender scene: write the story, find
the correct existing location, create the assets, write the scripts, place and
animate objects, set cameras, light it, render the shots.

**Continuity is the point.** Don't recreate locations that already exist. A
citizen's house stays their actual house at its actual address; a business
stays where it was built; roads and landmarks stay put. A viewer should be able
to see something in a Story and then go find that same spot on the website.

---

## 4. Don't try to make Pixar

Simple and intentional beats ambitious and broken. Design the story around
what Blender scripting reliably produces.

**Reliable:** vehicle drives / reverses / follows a path, wheels rotate, garage
or door or gate or box opens, object rises from the ground, construction
animation, sign changes, lights activate or flash or shut off, objects fall /
scatter / launch / roll / shake, camera tracks or pans or zooms, overhead
moves, smoke, sparks, rain, lightning, fog, simple water, particles, rigid-body
physics, simple environmental destruction, and objects appearing or
disappearing between cuts.

**Avoid stories that require:** people, character acting, realistic walking,
hand interaction, facial animation, crowds, character physics, or extremely
precise multi-object interaction.

If an action is hard to animate, **do not abandon the story — find a
filmmaking solution.** Cut around it. The viewer fills in the missing action.

Slightly mechanical movement is charming when the concept, framing, editing,
timing and sound are strong.

---

## 5. Editing is part of the storytelling

Nothing has to be shown continuously. Hard cuts, establishing shots, close-ups,
overhead reveals, before/after pairs, match cuts, reaction shots and implied
action are all in play. The human team assembles the final Reel; the AI's job
is to deliver **strong, usable, edit-friendly shots**.

Always suggest sound. It does more for simple animation than better animation
would: reverse beep, brake squeal, cardboard thump, box creak, a whoosh into
hundreds of quacks, alarms, thunder, the electrical clunk of lights dying.

---

## 6. Length, hook, numbering

**Length:** target roughly 10–20 seconds, and do not force uniformity. Nine
seconds is right if the joke lands in nine. Twenty-two is acceptable for a
strong story. Retention matters more than a fixed duration — every second needs
a reason to exist.

**Hook:** the first 1–2 seconds decide everything, and **the event is the
hook**. Never open with "Followville Stories Episode 4." Open with:

- "Someone just opened Followville's first post office…"
- "Something strange appeared outside this citizen's house."
- "Followville may have its first villain."
- "This package caused chaos in Followville."
- "Followville's newest business lasted about 10 seconds before this happened."

**Numbering:** `FOLLOWVILLE STORIES #001`, `#002`, `#003` — episode numbers,
not day numbers, because Stories are not daily. The number is secondary
branding for collectability; it is never the reason to watch.

**Structure:** HOOK → SETUP → ESCALATION → PAYOFF → optional CTA.

---

## 7. Story categories

Not every Story features a random citizen.

| Category | What it is |
| --- | --- |
| **Citizen** | Something happens around a randomly selected claimed home. |
| **Custom property** | A purchased custom build is revealed. |
| **Business** | A citizen-created business is involved in an event. |
| **Organization** | Postal service, weather service, the Followville Times, clubs, departments. |
| **City** | Storm, traffic, outage, construction, road closure, festival, new infrastructure, strange discovery. |
| **Government** | Mayor, City Hall, the election, a city project. |
| **Lore** | Villain lair, mystery, hidden object, unexplained event, running joke. |
| **Trend** | An internet trend adapted into the world, when it fits naturally. |
| **Sponsored** | A brand, business or artist integration. |

---

## 8. Citizen selection

Followville should maintain a pool of **registered citizens with claimed
homes**, from which a property can be drawn at random when a Story wants one.
The draw can occasionally be shown publicly as a wheel or randomizer — that is
what produces "that could be my house."

**Free citizens with claimed houses stay fully eligible. Selection is never
purchasable.** See §11.

The pool is derived, never maintained by hand: it comes from the Supabase
`claims`/`profiles` tables plus `world_state.json`, exactly like the map,
`/today` and `/house/:id`. **Never create a separate Story location file, a
parallel table, or hard-coded coordinates** — that is a standing repo rule and
it applies here too.

CTA shape: *"Claim your Followville home for a chance to appear in a future
Story."*

---

## 9. Custom properties and the build queue

The product is **"customize your permanent property in Followville,"** not "pay
us to make a Blender model." A custom build should become a recognizable,
permanent part of the world whenever technically possible.

Current working pricing, which may rise with demand:

- **$5** — basic custom property/build.
- **$10** — higher-detail custom property/build.
- **$20+** — higher demand or more complex builds, once the queue justifies it.

A visible queue is under consideration, sized by real production capacity: the
first ten slots at $5, later slots at $10. It should read as "only so many
custom properties can be produced at once," not as manufactured scarcity. It
may later simplify to BASIC / PREMIUM / RUSH.

**Once someone buys at a price, their price is locked.** A customer's price
never goes up because the queue got longer afterwards.

**A custom property arrives already owned.** It goes onto the website carrying
the buyer's handle, and **the buyer never goes and claims it** — it is theirs
the moment it exists. That is the opposite of the ordinary path, where a
follower's house appears unowned and they claim it. Practically: the `houses`
row stays `claimable = true` in kind, but the `claims` row is created for them
rather than by them, so `/house/:id` and the map show their name on arrival.
Attribution lives in the existing `claims` table like everyone else's —
**no separate custom-property table and no hard-coded names**, per the standing
rule.

One case still to decide, flagged rather than assumed: the one-house-per-account
DB constraint. If the custom build *replaces* the buyer's existing home — the
common case, and the one the reveal Story is built around — it is the same
house record and nothing conflicts. If someone buys a custom build at a *second*
address while keeping their home (a business, say), that needs either an
explicit exemption or a decision that businesses aren't held as houses.
Ask Cade before building the first one.

**Sponsored locations are never claimable.** A branded store is city furniture,
not property — no citizen owns it. Enforce it the way every other civic
building is enforced: add the type to `NON_CLAIMABLE_TYPES` in `sync_houses.py`
**and** to the `$NonClaimable` mirror in `grow_windows.ps1` (both lists exist
and must agree), which makes `claim_house()` raise `not_claimable` server-side.

**Reveal Stories** fall out of paid builds naturally — *"One citizen just
replaced their normal Followville house with THIS."* Existing house →
construction begins → structure rises → reveal → property name → cinematic
closer. It rewards the customer, demonstrates the product, and adds permanent
variety at the same time. Don't turn every Story into an advertisement; let
good builds sell themselves.

**Personal vs community.** A single citizen wanting a guaranteed building for
themselves is a paid build. A public addition with genuine broad support —
many likes, multiple independent requests, sustained discussion, community
accounts forming, real participation — can be added free. One person
repeatedly spamming a request is not community support.

---

## 10. Organizations

Citizen-created Followville organizations are Story material: postal services,
newspapers, weather services, businesses, clubs, political groups, fictional
departments.

They are **independently operated** and do not represent official Followville
views unless explicitly designated. Consistent organizations with real
community support may earn physical representation — an office, headquarters,
store, station, sign or facility. That means activity *outside* the website can
create consequences *inside* the world, which is an important part of what
Followville is.

---

## 11. Monetization guardrails

**Never build "pay to improve your odds."** Do not design chance-based paid
mechanics without explicitly reviewing the idea first.

Paid products deliver **guaranteed value**: a guaranteed custom property or
build, a guaranteed reveal if included, premium customization, a commissioned
landmark, a sponsored Story, a sponsored location. Subscriptions or memberships
can be explored later.

**Brand integrations** should eventually be a real advertising product priced
well above citizen build prices — and the model is *the sponsor becomes part of
Followville*, not "pause the Story to read a script." A beverage brand sponsors
a Story; Followville builds a high-quality branded store in the city; the Story
happens there — an opening, a delivery gone wrong, a celebration, a joke. The
location can persist in the world and on the website afterwards. Packages might
include the branded 3D location, a dedicated Story, brand tagging, sponsored-
content disclosure, website presence, branded vehicles/signs/props, and future
background appearances.

**Music** integrates the same way: a nightclub opening, a festival, a downtown
event, a city montage. An artist or label pays for their track to become part
of a Story, and the music has to make sense for the event.

**Protect the magic.** Followville must never become "pay money or you don't
matter." A normal citizen can follow, receive a home, register, claim it,
explore, participate, influence the community and potentially appear in a Story
without paying anything. Paid features add personalization, guaranteed
creation, premium detail and commercial placement — never basic belonging.

---

## 12. Workflow — what to do when Cade says "let's make a Story"

Triggers: "Let's make a Followville Story", "Story video", "New Followville
Story", "Make an episode", or anything clearly meaning this format.

**Enter Story mode. Do not start modifying Blender.**

**Step 1 — gather context.** Current city state from `world_state.json`,
existing locations, businesses, claimed properties, the organization or custom
build involved, reusable assets, relevant lore, sponsor if any, requested tone,
production limits.

**Step 2 — propose three concepts.** For each one give:

TITLE · HOOK · WHAT HAPPENS · PAYOFF · WHY A NON-FOLLOWER WOULD WATCH · HOW IT
CONNECTS TO FOLLOWVILLE · CTA · REQUIRED ASSETS · BLENDER FEASIBILITY ·
COMPLEXITY (LOW / MEDIUM / HIGH)

Favour concepts that are visually legible, funny or interesting, easy to
animate, short, surprising, reusable and connected to the persistent world.
**Do not begin major production until one is picked**, unless told to choose
and proceed automatically.

**Step 3 — storyboard the chosen concept**, 3–5 shots. Per shot: shot number,
approximate duration, camera, location, visible assets, what moves, how it
moves, environmental effects, purpose of the shot, transition, sound
suggestion, and text/VO if needed. Detailed enough to execute production
straight from it.

**Step 4 — produce** (see §13 for the mechanics): use the canonical area,
preserve existing geometry, reuse assets, build new ones in the established
pastel low-poly style, set cameras, animate only what's necessary, prefer
scripted keyframes, test before final render, render edit-friendly shots, and
don't touch unrelated parts of the city.

**Step 5 — hand off to editing.** Deliver the rendered clips plus recommended
clip order, timing, VO suggestion, on-screen text, caption, sound effects,
music direction and CTA. The human team assembles and publishes.

---

## 13. How this maps onto the existing pipeline

This section is the bridge between Cade's creative direction above and the
rules in `CLAUDE.md`. Read both.

**A Story render must never advance the world.** `--replay` re-animates the
current day and never touches `world_state.json` or the Blend, which makes it
the correct base for every Story shot. The precedent already exists:
`build_godzilla_attack()` in `neighborhood_blender.py` builds an entire
temporary destruction layer that runs *only* under `--replay --godzilla` and
changes no state, no GLBs and no saved scene. **Story-only set dressing —
packages, wreckage, temporary props, one-off vehicles, effects — follows that
same pattern.** So do the render-only cameras `housefront` and `day34fire`.

**Tag every Story prop `nb_render_only`, or it ships to the live website.**
This is the sharpest edge in the whole format. `grow_windows.ps1` runs
`export_web.py` in the *same* Blender invocation as the generator and then
commits and pushes `town.glb` — so a Story prop left untagged does not just
appear in a render, it becomes permanent town geometry on the public site.
`export_web.py` deletes every object carrying `obj["nb_render_only"] = True`
before it bakes the WORLD collection, and that tag is the only thing standing
between a temporary gag and a rubber duck welded to the city forever. Tag the
meshes, the text objects, the cars **and** the lamps.

Safer still, and what #001 does: produce Stories by invoking Blender directly
with the generator alone and **no `export_web.py` in the command**, against the
repo's Blend copy. Nothing can then be exported, committed or pushed by
accident. `--replay --focus-type finished` gives a fully-built static town —
`focus-type` matching no building type empties the rise batch, which is what
stops the day's houses popping up mid-shot.

**Ownership of what a Story leaves behind.** A paid custom property appears
already attributed to its buyer with no claim step; a sponsored location is
never claimable, via `NON_CLAIMABLE_TYPES` and its `grow_windows.ps1` mirror.
See §9 for both, including the one-house-per-account case still to decide.

**Permanent additions are a different act.** If a Story leaves something behind
— a business, a landmark, a branded store, a custom property — that is a real
world change and takes the full route: an addressed build in the generator, a
guarded growth run, `world_layout.py` declarations (`LANDMARK_FOOTPRINTS`,
`KEEP_OUT_REGIONS`, `LANDMARK_APPROACHES` as applicable), both geometry audits,
and a `[WORLD]` or `[BOTH]` TEAM_LOG line. An undeclared landmark reports as
*unaudited*, not failed — silence is not proof.

**Naming.** Story shots follow the established one-off camera convention:
`--cam story001NAME` for the camera preset and `--tag story_001_shot3` so the
clips land separately instead of overwriting each other.

**Cost.** Renders take 10–15 minutes each, and a Story is several shots. Run
them as background jobs writing `render_log.txt` and hand log-watching to a
Haiku subagent — never poll with the expensive model. One preview still per day
maximum.

**Style checks that still apply:** the visible-surface depth rule on every new
prop, review new repeated assets head-on *and* from both oblique sides, the
lighting numbers, and `check_world_geometry.py` before committing anything that
moves a landmark or road.

**Anonymity.** No real names on anything public. Story captions and CTAs use
Instagram handles or property names.

**Concurrency.** Codex may be working the same files. `git fetch` and re-read
before editing.

---

## 14. Quality control — ask before producing

If several answers are no, rethink the concept.

- Would someone who has never seen Followville understand this?
- Is something interesting happening within 1–2 seconds?
- Does it have a payoff?
- Can it actually be produced reliably in Blender?
- Can it be simplified?
- Does it look like Followville?
- Does it preserve the real city?
- Does it make the world feel alive?
- Would an existing citizen care?
- Does it create a reason to return? To claim a home?
- Could it create reusable assets or lore?
- Does it avoid looking like generic AI-generated content?
- Does it avoid unnecessary human characters?
- Is the monetization, if any, additive rather than intrusive?

---

## 15. The flywheel

Daily Growth video → a non-follower discovers Followville → follows → gets a
house → creates an account → claims the house → becomes eligible for Story
selection → watches Stories because their property could appear → comments and
shares and returns → some citizens buy customization → custom builds create
more interesting locations → locations generate Stories → organizations
generate Stories → Stories attract more non-followers → brands sponsor Stories
→ revenue improves the project → more people discover Followville → more
citizens → more city growth.

Both series feed each other. Neither replaces the other.

---

## 16. Creative direction, in one place

Don't chase hyper-realistic AI cinema. Make it look unmistakably like
**Followville** — the low-poly pastel city is the identity, and simple
animation is fine. Prioritize:

**world consistency + strong hook + simple visual story + good payoff +
reusable world-building + community connection**

over technical animation complexity. The goal is not to prove AI can animate
something complicated. The goal is to make Followville feel alive.
