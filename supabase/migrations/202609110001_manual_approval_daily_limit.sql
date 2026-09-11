-- Closed beta access: manual approval plus one interview start per Beijing calendar day.

alter table public.profiles
  drop constraint if exists profiles_account_status_check;

alter table public.profiles
  alter column account_status set default 'pending';

alter table public.profiles
  add constraint profiles_account_status_check
  check (account_status in ('pending', 'approved', 'rejected', 'suspended', 'deletion_pending', 'disabled'));

-- Existing accounts were created before the approval workflow. Keep them usable.
update public.profiles set account_status = 'approved' where account_status = 'active';

-- A user must never be able to approve their own account.
drop policy if exists profiles_owner_update on public.profiles;

create table public.daily_interview_allowances (
  user_id uuid not null references auth.users(id) on delete cascade,
  usage_date date not null default (timezone('Asia/Shanghai', now()))::date,
  reservation_id uuid not null,
  status text not null default 'reserved' check (status in ('reserved', 'started')),
  created_at timestamptz not null default timezone('utc', now()),
  started_at timestamptz,
  primary key (user_id, usage_date)
);

alter table public.daily_interview_allowances enable row level security;

create policy daily_allowance_owner_select
on public.daily_interview_allowances for select to authenticated
using ((select auth.uid()) = user_id);

create or replace function public.reserve_daily_interview(p_reservation_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  current_status text;
  today_local date := (timezone('Asia/Shanghai', now()))::date;
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
    and status = 'reserved' and created_at < timezone('utc', now()) - interval '10 minutes';

  insert into public.daily_interview_allowances (user_id, usage_date, reservation_id)
  values ((select auth.uid()), today_local, p_reservation_id)
  on conflict (user_id, usage_date) do nothing;

  if not found then
    return jsonb_build_object('allowed', false, 'reason', 'daily_limit_reached');
  end if;

  return jsonb_build_object('allowed', true, 'reason', 'reserved');
end;
$$;

create or replace function public.commit_daily_interview(p_reservation_id uuid)
returns boolean
language sql
security definer
set search_path = ''
as $$
  update public.daily_interview_allowances
  set status = 'started', started_at = timezone('utc', now())
  where user_id = (select auth.uid())
    and usage_date = (timezone('Asia/Shanghai', now()))::date
    and reservation_id = p_reservation_id
    and status = 'reserved'
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
