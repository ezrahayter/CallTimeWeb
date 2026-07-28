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

create policy "Authenticated users can read app_state"
  on app_state for select
  to authenticated
  using (true);

create policy "Authenticated users can update app_state"
  on app_state for update
  to authenticated
  using (true)
  with check (true);

create policy "Authenticated users can insert app_state"
  on app_state for insert
  to authenticated
  with check (true);

-- Enable realtime so teammates see each other's changes without refreshing.
alter publication supabase_realtime add table app_state;

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

create index if not exists people_phone_idx on people (phone) where phone is not null and phone <> '';
create index if not exists people_email_idx on people (lower(email)) where email is not null and email <> '';

alter table people enable row level security;

create policy "Authenticated users can read people"
  on people for select
  to authenticated
  using (true);

create policy "Authenticated users can insert people"
  on people for insert
  to authenticated
  with check (true);

create policy "Authenticated users can update people"
  on people for update
  to authenticated
  using (true)
  with check (true);

alter publication supabase_realtime add table people;

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

create policy "Authenticated users can read donations"
  on donations for select
  to authenticated
  using (true);

create policy "Authenticated users can insert donations"
  on donations for insert
  to authenticated
  with check (true);

create policy "Authenticated users can update donations"
  on donations for update
  to authenticated
  using (true)
  with check (true);

create policy "Authenticated users can delete donations"
  on donations for delete
  to authenticated
  using (true);

alter publication supabase_realtime add table donations;
