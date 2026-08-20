-- Privacy-preserving aggregate activity for the public homepage globe.
-- This table stores coarse rollups only. It must never contain raw IPs or precise home locations.

create table public.globe_activity_rollups (
  id uuid primary key default gen_random_uuid(),
  bucket_start timestamptz not null,
  region_code text,
  label text not null,
  lat numeric not null check (lat between -90 and 90),
  lon numeric not null check (lon between -180 and 180),
  active_count int not null check (active_count > 0),
  source text not null default 'observed_activity',
  created_at timestamptz not null default now(),
  unique(bucket_start, label, lat, lon)
);

create index globe_activity_recent_idx on public.globe_activity_rollups(bucket_start desc);

alter table public.globe_activity_rollups enable row level security;

create policy globe_activity_public_read
on public.globe_activity_rollups for select
using (bucket_start >= now() - interval '2 hours');

create policy globe_activity_admin_all
on public.globe_activity_rollups for all
using (public.is_content_admin())
with check (public.is_content_admin());

comment on table public.globe_activity_rollups is
'Coarse aggregate activity only. Do not store raw IP addresses or precise individual locations.';
