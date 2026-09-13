-- Fixed account-review choices and one current resume per account.

alter table public.profiles
  drop constraint if exists profiles_account_status_check;

update public.profiles
set account_status = 'approved'
where account_status::text in ('active', 'approve');

update public.profiles
set account_status = 'pending'
where account_status::text not in ('pending', 'approved', 'rejected', 'suspended', 'deletion_pending', 'disabled');

do $$
begin
  create type public.account_status_enum as enum (
    'pending',
    'approved',
    'rejected',
    'suspended',
    'deletion_pending',
    'disabled'
  );
exception
  when duplicate_object then null;
end
$$;

alter table public.profiles
  alter column account_status drop default;

alter table public.profiles
  alter column account_status type public.account_status_enum
  using account_status::text::public.account_status_enum;

alter table public.profiles
  alter column account_status set default 'pending'::public.account_status_enum;

with ranked as (
  select id, row_number() over (partition by user_id order by updated_at desc, created_at desc) as position
  from public.resumes
  where deleted_at is null
)
update public.resumes
set status = 'deleted', deleted_at = timezone('utc', now())
where id in (select id from ranked where position > 1);

create unique index if not exists resumes_one_current_per_user_idx
on public.resumes (user_id)
where deleted_at is null;
