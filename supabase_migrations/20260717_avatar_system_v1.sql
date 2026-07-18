-- Followville Avatar System v1
-- Web/backend only: adds validated, owner-only avatar persistence. It does not
-- touch houses, claims, ownership, world state, population, or town geometry.

begin;

alter table public.profiles add column if not exists avatar jsonb not null default
  '{"version":1,"skin":"peach","height":"adult","face":"classic","hair":"swept","outfit":"tailored","hat":"none","look":"custom"}'::jsonb;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.profiles'::regclass and conname = 'profiles_avatar_valid'
  ) then
    alter table public.profiles add constraint profiles_avatar_valid check (
      jsonb_typeof(avatar) = 'object'
      and octet_length(avatar::text) <= 512
      and avatar ?& array['version','skin','height','face','hair','outfit','hat','look']
      and avatar - array['version','skin','height','face','hair','outfit','hat','look'] = '{}'::jsonb
      and avatar->>'version' = '1'
      and avatar->>'skin' in ('porcelain','fair','peach','warm','honey','amber','bronze','cocoa','deep','espresso')
      and avatar->>'height' in ('kid','tween','teen','adult','tall')
      and avatar->>'face' in ('classic','round','oval','narrow','heart','square','soft','defined')
      and avatar->>'hair' in ('none','close_crop','tousled','swept','afro','long')
      and avatar->>'outfit' in ('tailored','striped','tee','field_jacket','weekend','active')
      and avatar->>'hat' in ('none','ranger_hood')
      and avatar->>'look' in ('custom','casual_day_f','casual_day_m','casual_sky_f','casual_sky_m','casual_lilac_f','casual_lilac_m','casual_bald','suit_f','suit_m','classy_f','classy_m','chef_f','chef_m','doctor_young_f','doctor_young_m','doctor_senior_f','doctor_senior_m','worker_f','worker_m','cowboy_f','cowboy_m','kimono_f','kimono_m','pirate_f','pirate_m','viking_f','viking_m','ninja_f','ninja_m','sand_ninja_f','sand_ninja_m','gold_knight_f','gold_knight_m','knight_m','elf','witch','wizard')
    );
  end if;
end $$;

drop policy if exists profiles_own_avatar_update on public.profiles;
create policy profiles_own_avatar_update on public.profiles
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

-- Column-level UPDATE keeps every other profile field server-controlled. The
-- table constraint remains the final allowlist even if a client skips the RPC.
revoke update on public.profiles from public, anon, authenticated;
grant update (avatar) on public.profiles to authenticated;

create or replace function public.update_my_avatar(p_avatar jsonb)
returns json
language plpgsql security invoker set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_input jsonb := coalesce(p_avatar, '{}'::jsonb);
  v_avatar jsonb;
  v_row public.profiles;
begin
  if v_uid is null then raise exception 'not_authenticated'; end if;
  if jsonb_typeof(v_input) <> 'object' or octet_length(v_input::text) > 512 then
    raise exception 'bad_avatar';
  end if;
  if exists (
    select 1 from jsonb_object_keys(v_input) as k(key)
    where k.key not in ('version','skin','height','face','hair','outfit','hat','look')
  ) then raise exception 'bad_avatar'; end if;
  if coalesce(v_input->>'version','1') <> '1'
     or coalesce(v_input->>'skin','peach') not in
       ('porcelain','fair','peach','warm','honey','amber','bronze','cocoa','deep','espresso')
     or coalesce(v_input->>'height','adult') not in ('kid','tween','teen','adult','tall')
     or coalesce(v_input->>'face','classic') not in
       ('classic','round','oval','narrow','heart','square','soft','defined')
     or coalesce(v_input->>'hair','swept') not in
       ('none','close_crop','tousled','swept','afro','long')
     or coalesce(v_input->>'outfit','tailored') not in
       ('tailored','striped','tee','field_jacket','weekend','active')
     or coalesce(v_input->>'hat','none') not in
       ('none','ranger_hood')
     or coalesce(v_input->>'look','custom') not in
       ('custom','casual_day_f','casual_day_m','casual_sky_f','casual_sky_m','casual_lilac_f','casual_lilac_m','casual_bald','suit_f','suit_m','classy_f','classy_m','chef_f','chef_m','doctor_young_f','doctor_young_m','doctor_senior_f','doctor_senior_m','worker_f','worker_m','cowboy_f','cowboy_m','kimono_f','kimono_m','pirate_f','pirate_m','viking_f','viking_m','ninja_f','ninja_m','sand_ninja_f','sand_ninja_m','gold_knight_f','gold_knight_m','knight_m','elf','witch','wizard') then
    raise exception 'bad_avatar';
  end if;
  v_avatar := jsonb_build_object(
    'version',1,
    'skin',coalesce(v_input->>'skin','peach'),
    'height',coalesce(v_input->>'height','adult'),
    'face',coalesce(v_input->>'face','classic'),
    'hair',coalesce(v_input->>'hair','swept'),
    'outfit',coalesce(v_input->>'outfit','tailored'),
    'hat',coalesce(v_input->>'hat','none'),
    'look',coalesce(v_input->>'look','custom')
  );
  update public.profiles set avatar = v_avatar where user_id = v_uid returning * into v_row;
  if not found then raise exception 'profile_missing'; end if;
  return row_to_json(v_row);
end $$;

revoke execute on function public.update_my_avatar(jsonb) from public, anon, authenticated;
grant execute on function public.update_my_avatar(jsonb) to authenticated, service_role;

commit;
