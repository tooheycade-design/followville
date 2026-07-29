-- Refresh facts that advanced after the Company OS review branch was cut.

begin;

create function company_ops.append_repository_memory_correction(
  p_old_id uuid,
  p_new_id uuid,
  p_body text,
  p_source_reference text,
  p_source_digest text,
  p_reason text
)
returns void
language plpgsql
set search_path = ''
as $$
declare
  v_old company_ops.memories%rowtype;
begin
  select memory.* into v_old
    from company_ops.memories memory
   where memory.id = p_old_id
     and memory.status = 'active'
   for update;
  if not found then
    raise exception 'active source memory % does not exist', p_old_id;
  end if;

  update company_ops.memories
     set status = 'superseded'
   where id = v_old.id;

  insert into company_ops.memories (
    id, organization_id, project_id, memory_type, category, subject, body,
    source_type, source_reference, source_digest, confidence, status, version,
    tags, audience_roles, created_by_type, created_by_id, expires_at,
    supersedes_id, correction_reason
  ) values (
    p_new_id, v_old.organization_id, v_old.project_id, v_old.memory_type,
    v_old.category, v_old.subject, p_body, 'repository', p_source_reference,
    p_source_digest, 'confirmed', 'active', v_old.version + 1, v_old.tags,
    v_old.audience_roles, 'system',
    '00000000-0000-4000-8000-000000000032'::uuid, null, v_old.id, p_reason
  );

  update company_ops.memories
     set superseded_by_id = p_new_id
   where id = v_old.id;
end;
$$;

select company_ops.append_repository_memory_correction(
  '31000000-0000-4000-8000-000000000001',
  '32000000-0000-4000-8000-000000000001',
  'Followville is at Day 27 with population 500, 560 building records, seed counter 561, and planned address 357 next.',
  'world_state.json@e1e4e663622cc43a15244406efb9f8e05abc645f#sha256:a5c8ce6e68fbd115114cb709b47f6d743c5b5414564cbcdee17a00736460c19e',
  'a5c8ce6e68fbd115114cb709b47f6d743c5b5414564cbcdee17a00736460c19e',
  'Canonical origin/main advanced from Day 24 to Day 27.'
);

select company_ops.append_repository_memory_correction(
  '31000000-0000-4000-8000-000000000003',
  '32000000-0000-4000-8000-000000000003',
  'Ordinary follower homes consume sequential planned addresses and increase population. Permanent civic or feature records can be non-population and non-claimable. Day 27 consumed addresses 321 through 356; address 357 is next.',
  'AGENTS.md@e1e4e663622cc43a15244406efb9f8e05abc645f#sha256:e67e1092cbbf1d12b09ab43120cdfce9be041ffdf16b5da4299237fc9f78f1db',
  'e67e1092cbbf1d12b09ab43120cdfce9be041ffdf16b5da4299237fc9f78f1db',
  'Canonical origin/main advanced through three growth days.'
);

select company_ops.append_repository_memory_correction(
  '31000000-0000-4000-8000-000000000004',
  '32000000-0000-4000-8000-000000000004',
  'The town includes the founder grid, downtown and Civic Square, the circular park district, Creekside Bend, Willow Hills, Twin Oaks, Kaleidoscope Crest, East Woods, and North Ridge. Planned districts reveal roads and lots only as growth consumes their addresses.',
  'AGENTS.md@e1e4e663622cc43a15244406efb9f8e05abc645f#sha256:e67e1092cbbf1d12b09ab43120cdfce9be041ffdf16b5da4299237fc9f78f1db',
  'e67e1092cbbf1d12b09ab43120cdfce9be041ffdf16b5da4299237fc9f78f1db',
  'East Woods and North Ridge are now canonical districts.'
);

select company_ops.append_repository_memory_correction(
  '31000000-0000-4000-8000-000000000005',
  '32000000-0000-4000-8000-000000000005',
  'Day 27 completed North Ridge with 14 homes on Ridgeview Drive, 16 on Bluebird Court, and six on Summit Court at addresses 321 through 356. Roads remain terrain-following and reveal only with occupied planned lots.',
  'AGENTS.md@e1e4e663622cc43a15244406efb9f8e05abc645f#sha256:e67e1092cbbf1d12b09ab43120cdfce9be041ffdf16b5da4299237fc9f78f1db',
  'e67e1092cbbf1d12b09ab43120cdfce9be041ffdf16b5da4299237fc9f78f1db',
  'Current road growth advanced from Larkspur Loop and Sunset Court.'
);

select company_ops.append_repository_memory_correction(
  '31000000-0000-4000-8000-000000000007',
  '32000000-0000-4000-8000-000000000007',
  'Permanent public places include Followville Elementary School, Follow Mart, Fire Station 1, City Hall, Civic Square, and Followville Cinema. The Day 26 construction vote site at seed 524 was converted in place into the permanent non-claimable cinema without adding a duplicate civic record or population.',
  'AGENTS.md@e1e4e663622cc43a15244406efb9f8e05abc645f#sha256:e67e1092cbbf1d12b09ab43120cdfce9be041ffdf16b5da4299237fc9f78f1db',
  'e67e1092cbbf1d12b09ab43120cdfce9be041ffdf16b5da4299237fc9f78f1db',
  'Followville Cinema became a permanent landmark.'
);

select company_ops.append_repository_memory_correction(
  '31000000-0000-4000-8000-000000000010',
  '32000000-0000-4000-8000-000000000010',
  'The authoritative Blender scene exports a complete town.glb safety copy plus a base chunk and 28 district or feature chunks described by town_manifest.json. Day 27 has exact 560-building coverage and validated state and asset hashes.',
  'AGENTS.md@e1e4e663622cc43a15244406efb9f8e05abc645f#sha256:e67e1092cbbf1d12b09ab43120cdfce9be041ffdf16b5da4299237fc9f78f1db',
  'e67e1092cbbf1d12b09ab43120cdfce9be041ffdf16b5da4299237fc9f78f1db',
  'The streamed asset set advanced from 23 to 28 chunks.'
);

select company_ops.append_repository_memory_correction(
  '31000000-0000-4000-8000-000000000015',
  '32000000-0000-4000-8000-000000000015',
  'The Day 24 browser depth preference remains part of the viewer, and subsequent guarded Day 25 through Day 27 rebuilds produced the current authoritative geometry. Re-open facade depth work only when current Day 27 visual evidence demonstrates a regression.',
  'AGENTS.md@e1e4e663622cc43a15244406efb9f8e05abc645f#sha256:e67e1092cbbf1d12b09ab43120cdfce9be041ffdf16b5da4299237fc9f78f1db',
  'e67e1092cbbf1d12b09ab43120cdfce9be041ffdf16b5da4299237fc9f78f1db',
  'The pending next guarded rebuild occurred during later canonical growth.'
);

drop function company_ops.append_repository_memory_correction(
  uuid, uuid, text, text, text, text
);

commit;
