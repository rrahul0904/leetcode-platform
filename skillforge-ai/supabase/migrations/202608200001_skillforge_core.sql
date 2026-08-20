create extension if not exists vector with schema extensions;
create extension if not exists pg_trgm with schema extensions;

create type public.app_role as enum ('free_user','pro_user','admin','content_reviewer','enterprise_admin','enterprise_member');
create type public.question_difficulty as enum ('Easy','Medium','Hard');
create type public.question_status as enum ('draft','review','published','blocked');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  role public.app_role not null default 'free_user',
  subscription_plan text not null default 'free',
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table public.topics (
  id uuid primary key default gen_random_uuid(), name text not null, slug text unique not null,
  description text, icon text, sort_order int not null default 0, created_at timestamptz not null default now()
);
create table public.subtopics (
  id uuid primary key default gen_random_uuid(), topic_id uuid not null references public.topics(id) on delete cascade,
  name text not null, slug text not null, description text, unique(topic_id, slug)
);
create table public.questions (
  id uuid primary key default gen_random_uuid(), public_id text unique not null, title text not null,
  topic_id uuid references public.topics(id), subtopic_id uuid references public.subtopics(id),
  difficulty public.question_difficulty not null, question_type text not null, body text not null,
  constraints jsonb not null default '[]'::jsonb, starter_code text, sample_input text, sample_output text,
  expected_output text, explanation_summary text, status public.question_status not null default 'draft',
  primary_language text not null default 'text', source_name text, source_path text, source_hash text,
  source_metadata jsonb not null default '{}'::jsonb,
  search_document tsvector generated always as (
    setweight(to_tsvector('english', coalesce(title,'')), 'A') || setweight(to_tsvector('english', coalesce(body,'')), 'B')
  ) stored,
  created_by uuid references public.profiles(id), created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create index questions_search_gin on public.questions using gin(search_document);
create index questions_title_trgm on public.questions using gin(title extensions.gin_trgm_ops);
create index questions_filter_idx on public.questions(status, difficulty, question_type, topic_id);
create table public.solutions (
  id uuid primary key default gen_random_uuid(), question_id uuid not null references public.questions(id) on delete cascade,
  language text, solution_body text not null, explanation text not null, time_complexity text, space_complexity text,
  common_mistakes jsonb not null default '[]'::jsonb, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique(question_id, language)
);
create table public.choices (
  id uuid primary key default gen_random_uuid(), question_id uuid not null references public.questions(id) on delete cascade,
  label text not null, body text not null, is_correct boolean not null default false, explanation text, unique(question_id,label)
);
create table public.tags (id uuid primary key default gen_random_uuid(), name text unique not null, slug text unique not null);
create table public.question_tags (
  question_id uuid references public.questions(id) on delete cascade, tag_id uuid references public.tags(id) on delete cascade,
  primary key(question_id, tag_id)
);
create table public.attempts (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references public.profiles(id) on delete cascade,
  question_id uuid not null references public.questions(id) on delete cascade, answer_body text, is_correct boolean,
  score numeric check(score is null or (score >= 0 and score <= 100)), runtime_ms int, memory_kb int, feedback text,
  created_at timestamptz not null default now()
);
create index attempts_user_created_idx on public.attempts(user_id, created_at desc);
create table public.bookmarks (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references public.profiles(id) on delete cascade,
  question_id uuid not null references public.questions(id) on delete cascade, created_at timestamptz not null default now(), unique(user_id, question_id)
);
create table public.progress (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references public.profiles(id) on delete cascade,
  topic_id uuid not null references public.topics(id) on delete cascade, completed_count int not null default 0,
  correct_count int not null default 0, streak_count int not null default 0,
  mastery_score numeric not null default 0 check(mastery_score between 0 and 100), last_activity_at timestamptz,
  unique(user_id, topic_id)
);
create table public.learning_paths (
  id uuid primary key default gen_random_uuid(), slug text unique not null, name text not null, description text,
  config jsonb not null default '{}'::jsonb, status text not null default 'published', created_at timestamptz not null default now()
);
create table public.ai_interactions (
  id uuid primary key default gen_random_uuid(), user_id uuid references public.profiles(id) on delete set null,
  question_id uuid references public.questions(id) on delete set null, interaction_type text not null,
  model_provider text, model_name text, prompt_tokens int, completion_tokens int, cost_estimate numeric, created_at timestamptz not null default now()
);
create table public.question_embeddings (
  id uuid primary key default gen_random_uuid(), question_id uuid not null references public.questions(id) on delete cascade,
  content_type text not null, content text not null, embedding extensions.vector(1536), metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(), unique(question_id, content_type)
);
create index question_embeddings_hnsw on public.question_embeddings using hnsw (embedding extensions.vector_cosine_ops);
create table public.import_jobs (
  id uuid primary key default gen_random_uuid(), created_by uuid references public.profiles(id), storage_path text not null,
  format text not null check(format in ('markdown','csv','json')), status text not null default 'uploaded',
  stats jsonb not null default '{}'::jsonb, error_report_path text, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);

create or replace function public.is_content_admin()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.profiles p where p.id = auth.uid() and p.role in ('admin','content_reviewer','enterprise_admin'));
$$;

create or replace function public.hybrid_question_search(
  query_text text, query_embedding extensions.vector(1536), match_count int default 20,
  semantic_weight real default 0.65, keyword_weight real default 0.35
)
returns table(question_id uuid, public_id text, title text, difficulty public.question_difficulty, score real)
language sql stable as $$
  with semantic as (
    select qe.question_id, 1 - (qe.embedding <=> query_embedding) as sim
    from public.question_embeddings qe join public.questions q on q.id = qe.question_id
    where q.status = 'published' order by qe.embedding <=> query_embedding limit greatest(match_count * 4, 40)
  ), keyword as (
    select q.id as question_id, ts_rank_cd(q.search_document, websearch_to_tsquery('english', query_text)) as rank
    from public.questions q where q.status='published' and q.search_document @@ websearch_to_tsquery('english', query_text)
    order by rank desc limit greatest(match_count * 4, 40)
  )
  select q.id, q.public_id, q.title, q.difficulty,
         ((coalesce(s.sim,0) * semantic_weight) + (coalesce(k.rank,0) * keyword_weight))::real as score
  from public.questions q left join semantic s on s.question_id=q.id left join keyword k on k.question_id=q.id
  where q.status='published' and (s.question_id is not null or k.question_id is not null)
  order by score desc limit match_count;
$$;

alter table public.profiles enable row level security;
alter table public.questions enable row level security;
alter table public.solutions enable row level security;
alter table public.choices enable row level security;
alter table public.attempts enable row level security;
alter table public.bookmarks enable row level security;
alter table public.progress enable row level security;
alter table public.ai_interactions enable row level security;
alter table public.import_jobs enable row level security;

create policy profiles_self_read on public.profiles for select using (id=auth.uid() or public.is_content_admin());
create policy profiles_self_update on public.profiles for update using (id=auth.uid()) with check(id=auth.uid());
create policy published_questions_read on public.questions for select using (status='published' or public.is_content_admin());
create policy admin_questions_all on public.questions for all using (public.is_content_admin()) with check(public.is_content_admin());
create policy published_solutions_read on public.solutions for select using (exists(select 1 from public.questions q where q.id=question_id and (q.status='published' or public.is_content_admin())));
create policy admin_solutions_all on public.solutions for all using (public.is_content_admin()) with check(public.is_content_admin());
create policy published_choices_read on public.choices for select using (exists(select 1 from public.questions q where q.id=question_id and (q.status='published' or public.is_content_admin())));
create policy own_attempts_read on public.attempts for select using(user_id=auth.uid());
create policy own_attempts_insert on public.attempts for insert with check(user_id=auth.uid());
create policy own_bookmarks_all on public.bookmarks for all using(user_id=auth.uid()) with check(user_id=auth.uid());
create policy own_progress_read on public.progress for select using(user_id=auth.uid());
create policy own_ai_interactions_read on public.ai_interactions for select using(user_id=auth.uid());
create policy admin_import_jobs_all on public.import_jobs for all using(public.is_content_admin()) with check(public.is_content_admin());
