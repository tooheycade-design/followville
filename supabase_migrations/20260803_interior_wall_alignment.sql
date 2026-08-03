-- Permit furniture centers to sit flush against the interior wall faces.
-- This changes validation bounds only; it does not update any claim row.

create or replace function public.update_my_customization(p_house_id bigint, p_customization jsonb)
returns json
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_input jsonb := coalesce(p_customization, '{}'::jsonb);
  v_existing jsonb;
  v_interior jsonb;
  v_customization jsonb;
  v_row public.claims;
begin
  if v_uid is null then raise exception 'not_authenticated'; end if;
  select customization into v_existing from public.claims
   where user_id = v_uid and house_id = p_house_id;
  if not found then raise exception 'not_your_house'; end if;
  if jsonb_typeof(v_input) <> 'object' or octet_length(v_input::text) > 8192 then
    raise exception 'bad_customization';
  end if;
  if exists (select 1 from jsonb_object_keys(v_input) as k(key)
             where k.key not in ('version','wall','roof','door','yard','interior')) then
    raise exception 'bad_customization';
  end if;
  if coalesce(v_input->>'version','1') not in ('1','2')
     or coalesce(v_input->>'wall','original') not in
        ('original','butter','sage','sky','blush','lavender','cream')
     or coalesce(v_input->>'roof','original') not in
        ('original','charcoal','cedar','slate','forest','plum')
     or coalesce(v_input->>'door','original') not in
        ('original','red','navy','teal','yellow','white')
     or coalesce(v_input->>'yard','none') not in
        ('none','flowers','tree','bench','flag') then
    raise exception 'bad_customization';
  end if;

  if v_input ? 'interior' then
    if jsonb_typeof(v_input->'interior') <> 'array'
       or jsonb_array_length(v_input->'interior') > 48
       or exists (select 1 from jsonb_array_elements(v_input->'interior') as item(value)
                  where jsonb_typeof(item.value) <> 'object')
       or exists (
         select 1 from jsonb_array_elements(v_input->'interior') as item(value),
              lateral jsonb_object_keys(case when jsonb_typeof(item.value)='object'
                then item.value else '{}'::jsonb end) as k(key)
          where k.key not in ('item','x','z','r')
       )
       or exists (
         select 1 from jsonb_array_elements(v_input->'interior') as item(value)
          where not (item.value ?& array['item','x','z','r'])
             or jsonb_typeof(item.value->'item') <> 'string'
             or jsonb_typeof(item.value->'x') <> 'number'
             or jsonb_typeof(item.value->'z') <> 'number'
             or jsonb_typeof(item.value->'r') <> 'number'
             or item.value->>'item' not in (
               'couch_l','couch_large','fireplace','shelf_large','rug','light_floor',
               'table_round_large','chair','stool','kitchen_sink','fridge','oven','drawer',
               'bed_king','bed_single','nightstand','table_lamp','bathroom_sink','toilet',
               'bathtub','washing_machine','houseplant','curtains_double','light_ceiling','door_double'
             )
             or abs((item.value->>'x')::numeric) > 8.55
             or abs((item.value->>'z')::numeric) > 6.55
             or (item.value->>'r')::numeric <> trunc((item.value->>'r')::numeric)
             or (item.value->>'r')::int not between 0 and 3
       ) then raise exception 'bad_customization'; end if;

    select coalesce(jsonb_agg(jsonb_build_object(
      'item',item.value->>'item',
      'x',round((item.value->>'x')::numeric*4)/4,
      'z',round((item.value->>'z')::numeric*4)/4,
      'r',(item.value->>'r')::int
    ) order by item.ordinality),'[]'::jsonb)
      into v_interior
      from jsonb_array_elements(v_input->'interior') with ordinality as item(value,ordinality);
  elsif jsonb_typeof(v_existing->'interior')='array' then
    v_interior := v_existing->'interior';
  end if;

  v_customization := jsonb_build_object(
    'version',2,
    'wall',coalesce(v_input->>'wall','original'),
    'roof',coalesce(v_input->>'roof','original'),
    'door',coalesce(v_input->>'door','original'),
    'yard',coalesce(v_input->>'yard','none')
  ) || case when v_interior is null then '{}'::jsonb
            else jsonb_build_object('interior',v_interior) end;

  update public.claims set customization=v_customization
   where user_id=v_uid and house_id=p_house_id returning * into v_row;
  return row_to_json(v_row);
end $$;

revoke execute on function public.update_my_customization(bigint,jsonb) from public, anon;
grant execute on function public.update_my_customization(bigint,jsonb) to authenticated;
