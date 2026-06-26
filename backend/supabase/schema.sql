-- Wayfare Supabase schema + Row-Level Security (Phase 3)
-- Run once in the Supabase SQL editor (or `supabase db push`) on a fresh project.
-- Safe to re-run: every statement is guarded with IF NOT EXISTS / OR REPLACE.

create extension if not exists vector;
create extension if not exists pgcrypto;  -- gen_random_uuid()

-- Tables created via a direct Postgres connection (rather than Supabase's
-- dashboard/migration flow) don't automatically pick up the usual default
-- grants to anon/authenticated/service_role — without these, every query
-- fails with "permission denied" before RLS policies are even evaluated.
grant usage on schema public to anon, authenticated, service_role;
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges in schema public grant all on sequences to anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

create table if not exists profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text,
  home_city text,
  default_currency text not null default 'USD',
  created_at timestamptz not null default now()
);

create table if not exists preferences (
  user_id uuid primary key references auth.users (id) on delete cascade,
  budget_style text,
  pace text,
  interests text[] not null default '{}',
  dietary text,
  updated_at timestamptz not null default now()
);

create table if not exists trips (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  title text,
  raw_query text not null,
  parsed jsonb,
  status text not null default 'pending',
  share_id uuid unique not null default gen_random_uuid(),
  created_at timestamptz not null default now()
);

create index if not exists trips_user_id_idx on trips (user_id);

create table if not exists trip_results (
  trip_id uuid primary key references trips (id) on delete cascade,
  flights jsonb not null default '[]',
  stays jsonb not null default '[]',
  activities jsonb not null default '[]',
  itinerary jsonb not null default '[]',
  budget jsonb,
  narrative_summary jsonb,
  llm_calls int not null default 0,
  llm_usage jsonb,
  selected_flight_offer_id text,
  selected_hotel_id text
);

alter table trip_results add column if not exists narrative_summary jsonb;
alter table trip_results add column if not exists llm_usage jsonb;
alter table trip_results add column if not exists selected_flight_offer_id text;
alter table trip_results add column if not exists selected_hotel_id text;

create table if not exists memory_chunks (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  content text not null,
  embedding vector(768),
  source_trip_id uuid references trips (id) on delete set null,
  created_at timestamptz not null default now()
);

create index if not exists memory_chunks_user_id_idx on memory_chunks (user_id);

create table if not exists tool_cache (
  key text primary key,
  value jsonb not null,
  expires_at timestamptz not null
);

-- Retroactive grants for tables that may already exist from an earlier apply
-- (the `alter default privileges` above only covers tables created after it).
grant all on profiles, preferences, trips, trip_results, memory_chunks, tool_cache
  to anon, authenticated, service_role;
grant usage, select on all sequences in schema public to anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Row-Level Security: every per-user table is locked to auth.uid().
--
-- The backend talks to Postgres with the service-role key (which bypasses RLS)
-- and itself filters every query by the JWT-verified user_id — see app/auth.py
-- and app/memory.py. RLS here is the defense-in-depth layer: if the anon key
-- + a user's JWT were ever used to query these tables directly (e.g. a future
-- frontend feature), this is what actually stops cross-user reads.
--
-- `GET /share/{share_id}` (public trip sharing) is served by the backend via
-- the service-role key, not by a public RLS policy — a public "anyone can
-- read this table" policy would let anyone enumerate every trip, not just the
-- one they have a share link for.
-- ---------------------------------------------------------------------------

alter table profiles enable row level security;
alter table preferences enable row level security;
alter table trips enable row level security;
alter table trip_results enable row level security;
alter table memory_chunks enable row level security;
alter table tool_cache enable row level security;  -- no policies: service-role only

drop policy if exists "profiles_select_own" on profiles;
create policy "profiles_select_own" on profiles for select using (auth.uid() = id);
drop policy if exists "profiles_insert_own" on profiles;
create policy "profiles_insert_own" on profiles for insert with check (auth.uid() = id);
drop policy if exists "profiles_update_own" on profiles;
create policy "profiles_update_own" on profiles for update using (auth.uid() = id);

drop policy if exists "preferences_select_own" on preferences;
create policy "preferences_select_own" on preferences for select using (auth.uid() = user_id);
drop policy if exists "preferences_insert_own" on preferences;
create policy "preferences_insert_own" on preferences for insert with check (auth.uid() = user_id);
drop policy if exists "preferences_update_own" on preferences;
create policy "preferences_update_own" on preferences for update using (auth.uid() = user_id);

drop policy if exists "trips_select_own" on trips;
create policy "trips_select_own" on trips for select using (auth.uid() = user_id);
drop policy if exists "trips_insert_own" on trips;
create policy "trips_insert_own" on trips for insert with check (auth.uid() = user_id);
drop policy if exists "trips_update_own" on trips;
create policy "trips_update_own" on trips for update using (auth.uid() = user_id);
drop policy if exists "trips_delete_own" on trips;
create policy "trips_delete_own" on trips for delete using (auth.uid() = user_id);

drop policy if exists "trip_results_select_own" on trip_results;
create policy "trip_results_select_own" on trip_results for select using (
  trip_id in (select id from trips where user_id = auth.uid())
);
drop policy if exists "trip_results_insert_own" on trip_results;
create policy "trip_results_insert_own" on trip_results for insert with check (
  trip_id in (select id from trips where user_id = auth.uid())
);
drop policy if exists "trip_results_update_own" on trip_results;
create policy "trip_results_update_own" on trip_results for update using (
  trip_id in (select id from trips where user_id = auth.uid())
);

drop policy if exists "memory_chunks_select_own" on memory_chunks;
create policy "memory_chunks_select_own" on memory_chunks for select using (auth.uid() = user_id);
drop policy if exists "memory_chunks_insert_own" on memory_chunks;
create policy "memory_chunks_insert_own" on memory_chunks for insert with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- Vector similarity search for memory recall (called via supabase.rpc(...)).
-- SECURITY INVOKER (default) + explicit user_id filter: safe to expose even
-- if ever called with the anon key + a user JWT, since it can only return
-- that caller's own rows once RLS is also in effect on memory_chunks.
-- ---------------------------------------------------------------------------

create or replace function match_memory_chunks(
  query_embedding vector(768),
  match_user_id uuid,
  match_count int default 5
)
returns table (id bigint, content text, source_trip_id uuid, similarity float)
language sql stable
as $$
  select
    memory_chunks.id,
    memory_chunks.content,
    memory_chunks.source_trip_id,
    1 - (memory_chunks.embedding <=> query_embedding) as similarity
  from memory_chunks
  where memory_chunks.user_id = match_user_id
  order by memory_chunks.embedding <=> query_embedding
  limit match_count;
$$;
