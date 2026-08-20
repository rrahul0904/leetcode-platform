-- SkillForge hardening: auth bootstrap, lookup-table RLS, keyword fallback search, and governed storage.

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'display_name', split_part(new.email, '@', 1)))
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

alter table public.topics enable row level security;
alter table public.subtopics enable row level security;
alter table public.tags enable row level security;
alter table public.question_tags enable row level security;
alter table public.learning_paths enable row level security;
alter table public.question_embeddings enable row level security;

create policy topics_public_read on public.topics for select using (true);
create policy subtopics_public_read on public.subtopics for select using (true);
create policy tags_public_read on public.tags for select using (true);
create policy question_tags_public_read on public.question_tags for select using (true);
create policy learning_paths_public_read on public.learning_paths for select using (status = 'published' or public.is_content_admin());

create policy topics_admin_all on public.topics for all using (public.is_content_admin()) with check (public.is_content_admin());
create policy subtopics_admin_all on public.subtopics for all using (public.is_content_admin()) with check (public.is_content_admin());
create policy tags_admin_all on public.tags for all using (public.is_content_admin()) with check (public.is_content_admin());
create policy question_tags_admin_all on public.question_tags for all using (public.is_content_admin()) with check (public.is_content_admin());
create policy learning_paths_admin_all on public.learning_paths for all using (public.is_content_admin()) with check (public.is_content_admin());
create policy embeddings_admin_all on public.question_embeddings for all using (public.is_content_admin()) with check (public.is_content_admin());

create or replace function public.keyword_question_search(
  query_text text,
  match_count int default 20
)
returns table(question_id uuid, public_id text, title text, difficulty public.question_difficulty, score real)
language sql
stable
as $$
  select
    q.id,
    q.public_id,
    q.title,
    q.difficulty,
    ts_rank_cd(q.search_document, websearch_to_tsquery('english', query_text))::real as score
  from public.questions q
  where q.status = 'published'
    and q.search_document @@ websearch_to_tsquery('english', query_text)
  order by score desc, q.public_id
  limit least(greatest(match_count, 1), 50);
$$;

grant execute on function public.keyword_question_search(text, int) to anon, authenticated;
grant execute on function public.hybrid_question_search(text, extensions.vector, int, real, real) to anon, authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('question-imports', 'question-imports', false, 52428800, array['text/csv','application/json','text/markdown','text/plain']),
  ('generated-exports', 'generated-exports', false, 52428800, array['application/json','text/csv','application/pdf'])
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

create policy question_imports_admin_read
on storage.objects for select
to authenticated
using (bucket_id = 'question-imports' and public.is_content_admin());

create policy question_imports_admin_write
on storage.objects for insert
to authenticated
with check (bucket_id = 'question-imports' and public.is_content_admin());

create policy question_imports_admin_update
on storage.objects for update
to authenticated
using (bucket_id = 'question-imports' and public.is_content_admin())
with check (bucket_id = 'question-imports' and public.is_content_admin());

create policy generated_exports_owner_read
on storage.objects for select
to authenticated
using (
  bucket_id = 'generated-exports'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy generated_exports_owner_write
on storage.objects for insert
to authenticated
with check (
  bucket_id = 'generated-exports'
  and (storage.foldername(name))[1] = auth.uid()::text
);
