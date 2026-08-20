-- Keep user progress derived from persisted attempts rather than browser-only demo state.

create or replace function public.apply_attempt_to_progress()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  target_topic uuid;
begin
  select topic_id into target_topic from public.questions where id = new.question_id;
  if target_topic is null then
    return new;
  end if;

  insert into public.progress (
    user_id,
    topic_id,
    completed_count,
    correct_count,
    streak_count,
    mastery_score,
    last_activity_at
  )
  values (
    new.user_id,
    target_topic,
    1,
    case when new.is_correct is true then 1 else 0 end,
    case when new.is_correct is true then 1 else 0 end,
    case when new.is_correct is true then 100 else 0 end,
    new.created_at
  )
  on conflict (user_id, topic_id) do update set
    completed_count = public.progress.completed_count + 1,
    correct_count = public.progress.correct_count + case when new.is_correct is true then 1 else 0 end,
    streak_count = case
      when new.is_correct is true then public.progress.streak_count + 1
      else 0
    end,
    mastery_score = round(
      ((public.progress.correct_count + case when new.is_correct is true then 1 else 0 end)::numeric
      / (public.progress.completed_count + 1)::numeric) * 100,
      2
    ),
    last_activity_at = new.created_at;

  return new;
end;
$$;

drop trigger if exists on_attempt_insert_progress on public.attempts;
create trigger on_attempt_insert_progress
after insert on public.attempts
for each row execute procedure public.apply_attempt_to_progress();

create policy own_progress_insert on public.progress
for insert with check (user_id = auth.uid());

create policy own_progress_update on public.progress
for update using (user_id = auth.uid()) with check (user_id = auth.uid());
