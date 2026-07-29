-- Initial Followville memory, derived only from canonical repository sources.

begin;

with target_projects as (
  select project.organization_id, project.id as project_id
    from company_ops.projects project
   where lower(project.name) like '%followville%'
      or lower(project.slug) like '%followville%'
), source_facts (
  memory_id, category, subject, body, source_reference, source_digest,
  confidence, tags, audience_roles
) as (
  values
  (
    '31000000-0000-4000-8000-000000000001'::uuid,
    'current_state',
    'Current canonical town state',
    'Followville is at Day 24 with population 400, 457 building records, seed counter 458, and planned address 257 next.',
    'world_state.json@sha256:65ab14f80c826fefa9a01404afbcc65e1da017931d4da61e9ae279ef74ddd8d9',
    '65ab14f80c826fefa9a01404afbcc65e1da017931d4da61e9ae279ef74ddd8d9',
    'confirmed', array['day-24','population','buildings','canonical-state'],
    array['owner','ceo','engineer','reviewer','researcher','growth','content']
  ),
  (
    '31000000-0000-4000-8000-000000000002'::uuid,
    'identity',
    'Followville product identity',
    'Followville is Cade''s persistent low-poly 3D Instagram town. Every follower is represented by a house, and daily reels show the town growing.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['instagram','followers','town','brand'],
    array['owner','ceo','researcher','growth','content']
  ),
  (
    '31000000-0000-4000-8000-000000000003'::uuid,
    'house_numbering',
    'House numbering and population rules',
    'Ordinary follower homes consume sequential planned addresses and increase population. Permanent civic or feature records can be non-population and non-claimable. Day 24 consumed addresses 228 through 256; address 257 is next.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['addresses','population','claimable','growth'],
    array['owner','ceo','engineer','reviewer','researcher','growth']
  ),
  (
    '31000000-0000-4000-8000-000000000004'::uuid,
    'town_layout',
    'Town layout and districts',
    'The town includes the founder grid, downtown and Civic Square, the circular park district, Creekside Bend, Willow Hills, Twin Oaks, and Kaleidoscope Crest. Planned districts reveal roads and lots only as growth consumes their addresses.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['layout','districts','neighborhoods','roads'],
    array['owner','ceo','engineer','reviewer','researcher','growth','content']
  ),
  (
    '31000000-0000-4000-8000-000000000005'::uuid,
    'roads',
    'Current road growth',
    'Day 24 completed Larkspur Loop at addresses 228 through 234 and opened Sunset Court at addresses 235 through 256. Roads are continuous authored or terrain-following surfaces and must not be revealed ahead of occupied planned lots.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['larkspur-loop','sunset-court','roads','day-24'],
    array['owner','engineer','reviewer','researcher','growth','content']
  ),
  (
    '31000000-0000-4000-8000-000000000006'::uuid,
    'founder_homes',
    'Founder homes',
    'The first ten custom homes are mushroom, casino, cat, castle, Eiffel home, hydrangea flower, Burj Khalifa, giant toilet, beach house, and cottage. Ordinary houses must never build in founder blocks.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['founders','custom-houses','protected-blocks'],
    array['owner','ceo','engineer','reviewer','researcher','growth','content']
  ),
  (
    '31000000-0000-4000-8000-000000000007'::uuid,
    'landmarks',
    'Permanent landmarks and civic places',
    'Permanent public places include Followville Elementary School, Follow Mart, Fire Station 1, City Hall, and Day 24 Civic Square beside City Hall. Civic Square is seed 428 at Blender coordinates (43,-134), website coordinates (43,134), and is non-claimable.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['landmarks','civic-square','city-hall','school','follow-mart'],
    array['owner','ceo','engineer','reviewer','researcher','growth','content']
  ),
  (
    '31000000-0000-4000-8000-000000000008'::uuid,
    'generation_rules',
    'Authoritative growth workflow',
    'Git is the executable source for code, world_state.json, website assets, and documentation. The shared authoritative scene is the iCloud neighborhood.blend, with a synchronized repo safety copy. Growth must use the guarded launcher and matching clean main/origin/main; --no-git and direct unguarded Blender growth are retired.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['git','blender','growth','world-state','safety'],
    array['owner','ceo','engineer','reviewer','researcher','growth']
  ),
  (
    '31000000-0000-4000-8000-000000000009'::uuid,
    'visual_style',
    'Visual and brand rules',
    'Followville is a polished low-poly town whose visible geometry must remain readable in portrait reels and the walkable browser. Preserve varied suburban designs, authored civic detail, restrained UI, and depth-stable separated surfaces; do not let temporary video spectacle become permanent canon.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['low-poly','visual-style','portrait','brand','canon'],
    array['owner','ceo','engineer','reviewer','researcher','growth','content']
  ),
  (
    '31000000-0000-4000-8000-000000000010'::uuid,
    'asset_library',
    'Blender and runtime assets',
    'The authoritative Blender scene exports a complete town.glb safety copy plus a base chunk and district chunks described by town_manifest.json. Day 24 has 23 streamed chunks, exact 457-building coverage, and hashes validated against canonical state.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['blender','glb','manifest','chunks','assets'],
    array['owner','engineer','reviewer','researcher','growth']
  ),
  (
    '31000000-0000-4000-8000-000000000011'::uuid,
    'website_architecture',
    'Public website architecture',
    'The public town is a static Vercel-hosted Three.js browser experience driven by world_state.json, town_manifest.json, streamed GLBs, and Supabase data. Detailed chunks load within 52 metres and unload beyond 84 metres; town.glb is the full fallback.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['website','threejs','vercel','streaming','performance'],
    array['owner','ceo','engineer','reviewer','researcher','growth']
  ),
  (
    '31000000-0000-4000-8000-000000000012'::uuid,
    'multiplayer',
    'Multiplayer and town chat',
    'The website uses Supabase Realtime Presence for online players and Broadcast for movement. Signed-in followers can send persistent town chat; authenticated RPCs and RLS protect identity, sessions, and chat writes.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['multiplayer','realtime','presence','chat','supabase'],
    array['owner','ceo','engineer','reviewer','researcher']
  ),
  (
    '31000000-0000-4000-8000-000000000013'::uuid,
    'authentication',
    'Authentication, claiming, and ownership',
    'Supabase Auth identifies followers. Claims attach an account to a stable house ID; ordinary accounts may own one house and trusted admins may own two. Claim and customization writes are authenticated RPCs enforced independently by database rules.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['auth','claiming','ownership','supabase'],
    array['owner','ceo','engineer','reviewer','researcher']
  ),
  (
    '31000000-0000-4000-8000-000000000014'::uuid,
    'customization',
    'Avatar and home customization',
    'Avatar System v1 provides 37 compact animated complete characters, body colour and height choices, guest persistence, and owner profile persistence. Homeowners can save exterior, roof/accent, and door palettes. Yard decorations are currently hidden and not rendered, while stored yard values are preserved.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['avatars','customization','homeowner','yard-paused'],
    array['owner','ceo','engineer','reviewer','researcher','growth']
  ),
  (
    '31000000-0000-4000-8000-000000000015'::uuid,
    'technical_debt',
    'Pending physical facade correction',
    'The browser depth-preference fix works with the current Day 24 GLBs. Blender source moves downtown glazing, transoms, and townhouse storefront assemblies 12mm outside their shells, but those physical corrections take effect only on the next guarded replay or growth rebuild.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['facades','depth','blender','next-rebuild','technical-debt'],
    array['owner','ceo','engineer','reviewer','researcher','growth']
  ),
  (
    '31000000-0000-4000-8000-000000000016'::uuid,
    'known_bugs',
    'Downtown walking issues resolved in Day 24',
    'The Day 24 walking pass moved the pale apron behind opaque walls, added landmark-specific hitboxes for Burj Khalifa, Follow Mart, Fire Station 1, and City Hall, smoothed camera collision, and reduced downtown chunk residency. Curbs were already accepted as good.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['resolved','downtown','hitboxes','camera','curbs'],
    array['owner','ceo','engineer','reviewer','researcher','growth']
  ),
  (
    '31000000-0000-4000-8000-000000000017'::uuid,
    'content_history',
    'Recent reel history',
    'Day 24 delivered a 20-second dusk portrait reveal with 29 homes, Civic Square, a temporary 400-person election joke, and fireworks. Day 23 featured City Hall; Day 22 featured Fire Station 1; Day 21 included the coffee truck. Temporary crowds, signs, effects, and destruction scenes are render-only.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['reels','day-24','hooks','fireworks','render-only'],
    array['owner','ceo','researcher','growth','content']
  ),
  (
    '31000000-0000-4000-8000-000000000018'::uuid,
    'idea_history',
    'Accepted, paused, and retired ideas',
    'Accepted systems include streamed town chunks, the live map, multiplayer, Homeowner Mode, Avatar System v1, and guarded growth. Yard decorations are paused. The taller modular avatar system, --no-git growth, iCloud-only execution, and automatic wip sharing are retired. Godzilla destruction and similar spectacle are render-only, not permanent town changes.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['decisions','accepted','paused','retired','render-only'],
    array['owner','ceo','engineer','reviewer','researcher','growth','content']
  ),
  (
    '31000000-0000-4000-8000-000000000019'::uuid,
    'priorities',
    'Current operating priorities',
    'Protect canonical state and ownership, keep guarded daily growth reproducible, keep the public walk smooth and depth-stable, preserve accurate collisions and streamed performance, and produce reviewed portrait content without leaking temporary reel elements into the permanent town.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'confirmed', array['priorities','safety','performance','growth','content'],
    array['owner','ceo','engineer','reviewer','researcher','growth','content']
  ),
  (
    '31000000-0000-4000-8000-000000000020'::uuid,
    'monetization',
    'Monetization requires an owner decision',
    'Canonical project documentation records no approved monetization model. Agents must not invent pricing, sponsorship, paid claiming, or commercial commitments; prepare options and route the decision to Cade and Zach.',
    'AGENTS.md@sha256:270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    '270a5e00f4b488d190c88eb972e5cfc97245dcf4f5c8e9c93d9e048b440e44bc',
    'requires_human_verification', array['monetization','owner-decision','do-not-invent'],
    array['owner','ceo','finance','researcher','growth']
  )
)
insert into company_ops.memories (
  id, organization_id, project_id, memory_type, category, subject, body,
  source_type, source_reference, source_digest, confidence, status, version,
  tags, audience_roles, created_by_type, created_by_id
)
select
  fact.memory_id, target.organization_id, target.project_id, 'project',
  fact.category, fact.subject, fact.body, 'repository', fact.source_reference,
  fact.source_digest, fact.confidence, 'active', 1, fact.tags,
  fact.audience_roles, 'system',
  '00000000-0000-4000-8000-000000000031'::uuid
from target_projects target
cross join source_facts fact
on conflict do nothing;

commit;
