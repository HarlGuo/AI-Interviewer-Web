-- AI Interviewer production data foundation.
-- Run this file in a new Supabase project. Every user-owned table is protected by RLS.

create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text check (char_length(display_name) <= 80),
  account_status text not null default 'active' check (account_status in ('active', 'deletion_pending', 'disabled')),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table public.user_consents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  consent_type text not null check (consent_type in ('terms', 'privacy', 'ai_processing', 'resume_processing', 'audio_processing')),
  document_version text not null check (char_length(document_version) between 1 and 40),
  accepted_at timestamptz not null default timezone('utc', now()),
  revoked_at timestamptz,
  unique (user_id, consent_type, document_version)
);

create table public.resumes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  file_name text not null check (char_length(file_name) between 1 and 255),
  object_path text unique,
  file_size_bytes bigint check (file_size_bytes between 1 and 10485760),
  file_sha256 text check (file_sha256 ~ '^[a-f0-9]{64}$'),
  status text not null default 'uploaded' check (status in ('uploaded', 'parsing', 'reviewed', 'confirmed', 'failed', 'deleted')),
  review_status text not null default 'pending' check (review_status in ('pending', 'ai_verified')),
  sections jsonb not null default '[]'::jsonb,
  warnings jsonb not null default '[]'::jsonb,
  confirmed_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (id, user_id)
);
create index resumes_user_created_idx on public.resumes (user_id, created_at desc);

create table public.target_roles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (char_length(title) between 1 and 120),
  job_description text not null default '' check (char_length(job_description) <= 20000),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (id, user_id)
);
create index target_roles_user_created_idx on public.target_roles (user_id, created_at desc);

create table public.interviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  resume_id uuid,
  target_role_id uuid,
  mode text not null check (mode in ('formal', 'focused')),
  focus text check (focus in ('self-introduction', 'resume-deep-dive', 'behavioral', 'role-specific')),
  status text not null default 'draft' check (status in ('draft', 'active', 'paused', 'completed', 'ended-early', 'failed')),
  target_title_snapshot text not null check (char_length(target_title_snapshot) between 1 and 120),
  job_description_snapshot text not null default '' check (char_length(job_description_snapshot) <= 20000),
  total_main_questions smallint not null default 0 check (total_main_questions between 0 and 30),
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (id, user_id),
  foreign key (resume_id, user_id) references public.resumes(id, user_id) on delete set null (resume_id),
  foreign key (target_role_id, user_id) references public.target_roles(id, user_id) on delete set null (target_role_id)
);
create index interviews_user_updated_idx on public.interviews (user_id, updated_at desc);

create table public.interview_questions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  interview_id uuid not null,
  external_question_id text not null,
  sequence_no smallint not null check (sequence_no between 1 and 100),
  stage text not null check (char_length(stage) between 1 and 80),
  question_text text not null check (char_length(question_text) between 1 and 12000),
  is_follow_up boolean not null default false,
  main_question_index smallint not null check (main_question_index between 0 and 30),
  follow_up_count smallint not null default 0 check (follow_up_count between 0 and 2),
  resume_evidence text not null default '',
  created_at timestamptz not null default timezone('utc', now()),
  unique (id, user_id),
  foreign key (interview_id, user_id) references public.interviews(id, user_id) on delete cascade,
  unique (interview_id, external_question_id),
  unique (interview_id, sequence_no)
);
create index interview_questions_interview_idx on public.interview_questions (interview_id, sequence_no);

create table public.interview_answers (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  interview_id uuid not null,
  question_id uuid not null,
  answer_text text not null check (char_length(answer_text) between 1 and 12000),
  source text not null default 'text' check (source in ('text', 'speech_transcript')),
  confirmed_by_user boolean not null default true,
  submitted_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (question_id),
  foreign key (interview_id, user_id) references public.interviews(id, user_id) on delete cascade,
  foreign key (question_id, user_id) references public.interview_questions(id, user_id) on delete cascade
);
create index interview_answers_interview_idx on public.interview_answers (interview_id, submitted_at);

create table public.interview_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  interview_id uuid not null unique,
  status text not null default 'generating' check (status in ('generating', 'completed', 'failed')),
  report_data jsonb,
  model_name text,
  rubric_version text,
  generated_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  foreign key (interview_id, user_id) references public.interviews(id, user_id) on delete cascade
);
create index interview_reports_user_created_idx on public.interview_reports (user_id, created_at desc);

create table public.ai_usage_events (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  interview_id uuid,
  operation text not null check (operation in ('resume_review', 'question_generation', 'answer_analysis', 'report_generation')),
  provider text not null,
  model_name text not null,
  request_id text,
  prompt_tokens integer check (prompt_tokens >= 0),
  completion_tokens integer check (completion_tokens >= 0),
  latency_ms integer check (latency_ms >= 0),
  outcome text not null check (outcome in ('succeeded', 'failed', 'timed_out')),
  error_code text,
  created_at timestamptz not null default timezone('utc', now()),
  foreign key (interview_id, user_id) references public.interviews(id, user_id) on delete set null (interview_id)
);
create index ai_usage_events_user_created_idx on public.ai_usage_events (user_id, created_at desc);

create table public.account_deletion_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  status text not null default 'pending' check (status in ('pending', 'processing', 'completed', 'failed', 'cancelled')),
  requested_at timestamptz not null default timezone('utc', now()),
  completed_at timestamptz,
  failure_code text
);
create unique index account_deletion_one_open_idx on public.account_deletion_requests (user_id) where status in ('pending', 'processing');

create table public.audit_events (
  id bigint generated always as identity primary key,
  user_id uuid references auth.users(id) on delete set null,
  action text not null check (char_length(action) between 1 and 100),
  resource_type text not null check (char_length(resource_type) between 1 and 60),
  resource_id text,
  result text not null check (result in ('succeeded', 'denied', 'failed')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);
create index audit_events_user_created_idx on public.audit_events (user_id, created_at desc);

create or replace function public.create_profile_for_new_user()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (user_id) values (new.id);
  return new;
end;
$$;
create trigger create_profile_after_signup after insert on auth.users
for each row execute function public.create_profile_for_new_user();

create trigger profiles_updated_at before update on public.profiles for each row execute function public.set_updated_at();
create trigger resumes_updated_at before update on public.resumes for each row execute function public.set_updated_at();
create trigger target_roles_updated_at before update on public.target_roles for each row execute function public.set_updated_at();
create trigger interviews_updated_at before update on public.interviews for each row execute function public.set_updated_at();
create trigger interview_answers_updated_at before update on public.interview_answers for each row execute function public.set_updated_at();
create trigger interview_reports_updated_at before update on public.interview_reports for each row execute function public.set_updated_at();

alter table public.profiles enable row level security;
alter table public.user_consents enable row level security;
alter table public.resumes enable row level security;
alter table public.target_roles enable row level security;
alter table public.interviews enable row level security;
alter table public.interview_questions enable row level security;
alter table public.interview_answers enable row level security;
alter table public.interview_reports enable row level security;
alter table public.ai_usage_events enable row level security;
alter table public.account_deletion_requests enable row level security;
alter table public.audit_events enable row level security;

create policy profiles_owner_select on public.profiles for select to authenticated using ((select auth.uid()) = user_id);
create policy profiles_owner_update on public.profiles for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy consents_owner_select on public.user_consents for select to authenticated using ((select auth.uid()) = user_id);
create policy consents_owner_insert on public.user_consents for insert to authenticated with check ((select auth.uid()) = user_id);
create policy consents_owner_update on public.user_consents for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create policy resumes_owner_all on public.resumes for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy target_roles_owner_all on public.target_roles for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy interviews_owner_all on public.interviews for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy questions_owner_all on public.interview_questions for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy answers_owner_all on public.interview_answers for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy reports_owner_select on public.interview_reports for select to authenticated using ((select auth.uid()) = user_id);
create policy usage_owner_select on public.ai_usage_events for select to authenticated using ((select auth.uid()) = user_id);
create policy deletion_owner_select on public.account_deletion_requests for select to authenticated using ((select auth.uid()) = user_id);
create policy deletion_owner_insert on public.account_deletion_requests for insert to authenticated with check ((select auth.uid()) = user_id);

-- Private PDF bucket. File names must be: <auth-user-uuid>/<resume-uuid>.pdf
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('resumes', 'resumes', false, 10485760, array['application/pdf'])
on conflict (id) do update set public = false, file_size_limit = 10485760, allowed_mime_types = array['application/pdf'];

create policy resume_files_owner_select on storage.objects for select to authenticated
using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy resume_files_owner_insert on storage.objects for insert to authenticated
with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy resume_files_owner_update on storage.objects for update to authenticated
using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text)
with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy resume_files_owner_delete on storage.objects for delete to authenticated
using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);
