-- Call Time — Supabase schema
-- Run this once in your Supabase project: Dashboard → SQL Editor → New query → paste → Run

create table if not exists app_state (
  id text primary key,
  data jsonb not null default '{"lists": []}'::jsonb,
  updated_at timestamptz not null default now()
);

-- Seed the single shared row the app reads/writes.
insert into app_state (id, data)
values ('main', '{"lists": []}'::jsonb)
on conflict (id) do nothing;

-- Lock the table down: only signed-in users (your team) can read or write.
alter table app_state enable row level security;

drop policy if exists "Authenticated users can read app_state" on app_state;
create policy "Authenticated users can read app_state"
  on app_state for select
  to authenticated
  using (true);

drop policy if exists "Authenticated users can update app_state" on app_state;
create policy "Authenticated users can update app_state"
  on app_state for update
  to authenticated
  using (true)
  with check (true);

drop policy if exists "Authenticated users can insert app_state" on app_state;
create policy "Authenticated users can insert app_state"
  on app_state for insert
  to authenticated
  with check (true);

-- Enable realtime so teammates see each other's changes without refreshing.
do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'app_state'
  ) then
    alter publication supabase_realtime add table app_state;
  end if;
end $$;

-- To add teammates: Supabase Dashboard → Authentication → Users → Add user
-- (set an email + password for each person; no public sign-up form is exposed by this app).

-- ---------------------------------------------------------------------------
-- Master contact directory — persists across lists, so contacts added to any
-- one list can be reused when building future lists.
-- ---------------------------------------------------------------------------
create table if not exists people (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  phone text,
  email text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Every candidate-list id this person has ever been added to, so the master
-- list can show list history even after they're removed from a list.
alter table people add column if not exists list_history jsonb not null default '[]'::jsonb;

alter table people add column if not exists address text;
alter table people add column if not exists organization text;
alter table people add column if not exists occupation text;

create index if not exists people_phone_idx on people (phone) where phone is not null and phone <> '';
create index if not exists people_email_idx on people (lower(email)) where email is not null and email <> '';

alter table people enable row level security;

drop policy if exists "Authenticated users can read people" on people;
create policy "Authenticated users can read people"
  on people for select
  to authenticated
  using (true);

drop policy if exists "Authenticated users can insert people" on people;
create policy "Authenticated users can insert people"
  on people for insert
  to authenticated
  with check (true);

drop policy if exists "Authenticated users can update people" on people;
create policy "Authenticated users can update people"
  on people for update
  to authenticated
  using (true)
  with check (true);

-- Needed so duplicate records can be removed after merging them together.
drop policy if exists "Authenticated users can delete people" on people;
create policy "Authenticated users can delete people"
  on people for delete
  to authenticated
  using (true);

do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'people'
  ) then
    alter publication supabase_realtime add table people;
  end if;
end $$;

-- Donation / pledge history per person, independent of any one list —
-- lets you log past gifts (including ones that predate this app) and see
-- someone's full giving history when you pull them into a new list.
create table if not exists donations (
  id uuid primary key default gen_random_uuid(),
  person_id uuid not null references people(id) on delete cascade,
  amount numeric,
  donated_on date,
  note text,
  created_at timestamptz not null default now()
);

create index if not exists donations_person_idx on donations (person_id);

alter table donations enable row level security;

drop policy if exists "Authenticated users can read donations" on donations;
create policy "Authenticated users can read donations"
  on donations for select
  to authenticated
  using (true);

drop policy if exists "Authenticated users can insert donations" on donations;
create policy "Authenticated users can insert donations"
  on donations for insert
  to authenticated
  with check (true);

drop policy if exists "Authenticated users can update donations" on donations;
create policy "Authenticated users can update donations"
  on donations for update
  to authenticated
  using (true)
  with check (true);

drop policy if exists "Authenticated users can delete donations" on donations;
create policy "Authenticated users can delete donations"
  on donations for delete
  to authenticated
  using (true);

do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'donations'
  ) then
    alter publication supabase_realtime add table donations;
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Possible-duplicate flags — pairs of people the team has flagged as maybe
-- being the same person (e.g. same name, added on different lists) but
-- hasn't merged yet. 'dismissed' means someone already confirmed they're
-- different people, so we stop asking about that pair.
-- ---------------------------------------------------------------------------
create table if not exists possible_duplicates (
  id uuid primary key default gen_random_uuid(),
  person_a uuid not null references people(id) on delete cascade,
  person_b uuid not null references people(id) on delete cascade,
  status text not null default 'pending',
  created_at timestamptz not null default now(),
  unique (person_a, person_b)
);

create index if not exists possible_duplicates_person_a_idx on possible_duplicates (person_a);
create index if not exists possible_duplicates_person_b_idx on possible_duplicates (person_b);

alter table possible_duplicates enable row level security;

drop policy if exists "Authenticated users can read possible_duplicates" on possible_duplicates;
create policy "Authenticated users can read possible_duplicates"
  on possible_duplicates for select
  to authenticated
  using (true);

drop policy if exists "Authenticated users can insert possible_duplicates" on possible_duplicates;
create policy "Authenticated users can insert possible_duplicates"
  on possible_duplicates for insert
  to authenticated
  with check (true);

drop policy if exists "Authenticated users can update possible_duplicates" on possible_duplicates;
create policy "Authenticated users can update possible_duplicates"
  on possible_duplicates for update
  to authenticated
  using (true)
  with check (true);

drop policy if exists "Authenticated users can delete possible_duplicates" on possible_duplicates;
create policy "Authenticated users can delete possible_duplicates"
  on possible_duplicates for delete
  to authenticated
  using (true);

do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'possible_duplicates'
  ) then
    alter publication supabase_realtime add table possible_duplicates;
  end if;
end $$;

-- Make sure the API layer picks up the tables/policies immediately.
notify pgrst, 'reload schema';
