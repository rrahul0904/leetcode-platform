create type public.source_rights_state as enum (
  'HOSTABLE_LICENSED',
  'EXTERNAL_REFERENCE_ONLY',
  'RIGHTS_REVIEW_REQUIRED',
  'REJECTED_PROPRIETARY'
);

create table public.content_sources (
  id uuid primary key default gen_random_uuid(),
  source_key text unique not null,
  display_name text not null,
  archive_name text,
  rights_state public.source_rights_state not null,
  license_name text,
  source_url text,
  source_hash text,
  notes text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.companies (
  id uuid primary key default gen_random_uuid(),
  canonical_name text unique not null,
  slug text unique not null,
  aliases text[] not null default '{}',
  created_at timestamptz not null default now()
);

create table public.question_source_observations (
  id uuid primary key default gen_random_uuid(),
  question_id uuid references public.questions(id) on delete cascade,
  source_id uuid not null references public.content_sources(id) on delete cascade,
  external_problem_id text,
  external_title text,
  external_url text,
  observed_difficulty text,
  observed_acceptance numeric,
  observed_frequency numeric,
  recency_window text,
  metadata jsonb not null default '{}'::jsonb,
  observed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(source_id, external_problem_id, recency_window, external_url)
);

create table public.question_company_observations (
  id uuid primary key default gen_random_uuid(),
  question_id uuid references public.questions(id) on delete cascade,
  company_id uuid not null references public.companies(id) on delete cascade,
  source_id uuid not null references public.content_sources(id) on delete cascade,
  recency_window text,
  frequency numeric,
  observation_count int not null default 1,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(question_id, company_id, source_id, recency_window)
);

create table public.solution_variants (
  id uuid primary key default gen_random_uuid(),
  question_id uuid not null references public.questions(id) on delete cascade,
  source_id uuid not null references public.content_sources(id) on delete restrict,
  language text not null,
  approach_name text,
  source_code text,
  explanation text,
  time_complexity text,
  space_complexity text,
  attribution text,
  publication_allowed boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(question_id, source_id, language, approach_name)
);

create index source_observations_question_idx on public.question_source_observations(question_id);
create index source_observations_external_idx on public.question_source_observations(external_problem_id);
create index company_observations_question_idx on public.question_company_observations(question_id);
create index company_observations_company_idx on public.question_company_observations(company_id);

alter table public.content_sources enable row level security;
alter table public.companies enable row level security;
alter table public.question_source_observations enable row level security;
alter table public.question_company_observations enable row level security;
alter table public.solution_variants enable row level security;

create policy content_sources_public_read on public.content_sources for select using (true);
create policy companies_public_read on public.companies for select using (true);
create policy source_observations_public_read on public.question_source_observations for select using (
  question_id is null or exists(select 1 from public.questions q where q.id = question_id and (q.status='published' or public.is_content_admin()))
);
create policy company_observations_public_read on public.question_company_observations for select using (
  question_id is null or exists(select 1 from public.questions q where q.id = question_id and (q.status='published' or public.is_content_admin()))
);
create policy solution_variants_public_read on public.solution_variants for select using (
  publication_allowed is true
  and exists(select 1 from public.questions q where q.id = question_id and q.status='published')
);

create policy content_sources_admin_all on public.content_sources for all using (public.is_content_admin()) with check (public.is_content_admin());
create policy companies_admin_all on public.companies for all using (public.is_content_admin()) with check (public.is_content_admin());
create policy source_observations_admin_all on public.question_source_observations for all using (public.is_content_admin()) with check (public.is_content_admin());
create policy company_observations_admin_all on public.question_company_observations for all using (public.is_content_admin()) with check (public.is_content_admin());
create policy solution_variants_admin_all on public.solution_variants for all using (public.is_content_admin()) with check (public.is_content_admin());
