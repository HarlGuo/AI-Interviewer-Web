-- Make the daily interview reservation idempotent for a single start request.
-- Same reservation_id (client interview id) may retry; a different interview still hits the daily limit.

create or replace function public.reserve_daily_interview(p_reservation_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  current_status text;
  today_local date := (timezone('Asia/Shanghai', now()))::date;
  existing_id uuid;
  existing_row_status text;
begin
  if (select auth.uid()) is null then
    raise exception 'authentication required';
  end if;
  select account_status into current_status
  from public.profiles
  where user_id = (select auth.uid());

  if current_status is distinct from 'approved' then
    return jsonb_build_object('allowed', false, 'reason', coalesce(current_status, 'pending'));
  end if;

  delete from public.daily_interview_allowances
  where user_id = (select auth.uid()) and usage_date = today_local
    and status = 'reserved'
    and reservation_id is distinct from p_reservation_id
    and created_at < timezone('utc', now()) - interval '10 minutes';

  insert into public.daily_interview_allowances (user_id, usage_date, reservation_id)
  values ((select auth.uid()), today_local, p_reservation_id)
  on conflict (user_id, usage_date) do nothing;

  select reservation_id, status
    into existing_id, existing_row_status
  from public.daily_interview_allowances
  where user_id = (select auth.uid()) and usage_date = today_local;

  if existing_id = p_reservation_id then
    return jsonb_build_object(
      'allowed', true,
      'reason', case when existing_row_status = 'started' then 'already_started' else 'reserved' end
    );
  end if;

  return jsonb_build_object('allowed', false, 'reason', 'daily_limit_reached');
end;
$$;

create or replace function public.commit_daily_interview(p_reservation_id uuid)
returns boolean
language sql
security definer
set search_path = ''
as $$
  update public.daily_interview_allowances
  set status = 'started',
      started_at = coalesce(started_at, timezone('utc', now()))
  where user_id = (select auth.uid())
    and usage_date = (timezone('Asia/Shanghai', now()))::date
    and reservation_id = p_reservation_id
    and status in ('reserved', 'started')
  returning true;
$$;

create or replace function public.release_daily_interview(p_reservation_id uuid)
returns boolean
language sql
security definer
set search_path = ''
as $$
  delete from public.daily_interview_allowances
  where user_id = (select auth.uid())
    and usage_date = (timezone('Asia/Shanghai', now()))::date
    and reservation_id = p_reservation_id
    and status = 'reserved'
  returning true;
$$;

revoke all on function public.reserve_daily_interview(uuid) from public, anon;
revoke all on function public.commit_daily_interview(uuid) from public, anon;
revoke all on function public.release_daily_interview(uuid) from public, anon;
grant execute on function public.reserve_daily_interview(uuid) to authenticated;
grant execute on function public.commit_daily_interview(uuid) to authenticated;
grant execute on function public.release_daily_interview(uuid) to authenticated;
