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
