-- First-party product analytics for the closed Web beta.
-- Raw product events and model usage are service-role only; no resume,
-- question, answer, recording or prompt content belongs in these tables.

create table if not exists public.analytics_events (
  event_id uuid primary key,
  event_name text not null check (event_name in (
    'landing_viewed', 'registration_submitted', 'registration_created', 'registration_failed',
    'account_approved', 'authenticated_session_started', 'sign_in_succeeded', 'sign_in_failed',
    'resume_upload_started', 'resume_upload_succeeded', 'resume_upload_failed',
    'resume_parse_started', 'resume_parse_succeeded', 'resume_parse_failed', 'resume_confirmed',
    'interview_entry_viewed', 'interview_mode_selected', 'interview_config_completed',
    'interview_start_requested', 'interview_started', 'interview_start_failed',
    'question_presented', 'answer_submit_requested', 'answer_accepted', 'answer_failed',
    'followup_triggered', 'interview_paused', 'interview_resumed',
    'interview_ended_early', 'interview_completed', 'interview_abandoned',
    'recording_started', 'recording_stopped', 'transcription_succeeded', 'transcription_failed',
    'report_generation_started', 'report_generation_succeeded', 'report_generation_failed',
    'report_viewed', 'report_advice_viewed',
    'feedback_prompt_viewed', 'feedback_skipped', 'feedback_submitted'
  )),
  user_id uuid references auth.users(id) on delete set null,
  session_id uuid not null,
  interview_id uuid,
  occurred_at timestamptz not null,
  received_at timestamptz not null default timezone('utc', now()),
  page text not null default '' check (char_length(page) <= 120),
  app_version text not null default 'unknown' check (char_length(app_version) between 1 and 80),
  source text not null default 'client' check (source in ('client', 'server')),
  properties jsonb not null default '{}'::jsonb
    check (jsonb_typeof(properties) = 'object' and octet_length(properties::text) <= 4096),
  foreign key (interview_id, user_id) references public.interviews(id, user_id) on delete set null (interview_id)
);
create index if not exists analytics_events_name_received_idx on public.analytics_events (event_name, received_at desc);
create index if not exists analytics_events_user_received_idx on public.analytics_events (user_id, received_at desc);
create index if not exists analytics_events_interview_idx on public.analytics_events (interview_id, received_at);

create table if not exists public.acquisition_attributions (
  user_id uuid primary key references auth.users(id) on delete cascade,
  landing_session_id uuid not null,
  utm_source text not null default 'direct' check (char_length(utm_source) between 1 and 80),
  utm_medium text not null default 'none' check (char_length(utm_medium) between 1 and 80),
  utm_campaign text not null default 'none' check (char_length(utm_campaign) between 1 and 120),
  utm_content text not null default 'none' check (char_length(utm_content) between 1 and 120),
  first_landed_at timestamptz not null,
  registered_at timestamptz not null default timezone('utc', now()),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.feedback_responses (
  interview_id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  satisfaction_score smallint not null check (satisfaction_score between 1 and 5),
  payment_willingness text not null check (payment_willingness in ('willing', 'depends_on_price', 'unwilling', 'prefer_not_to_say')),
  tags text[] not null default '{}'::text[]
    check (tags <@ array['问题贴合简历', '追问有深度', '等待太久', '语音体验不顺', '问题重复']::text[]),
  comment text not null default '' check (char_length(comment) <= 500),
  completion_type text not null check (completion_type in ('completed', 'ended_early')),
  app_version text not null default 'unknown' check (char_length(app_version) between 1 and 80),
  agent_version text not null default 'unknown' check (char_length(agent_version) between 1 and 80),
  submitted_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  foreign key (interview_id, user_id) references public.interviews(id, user_id) on delete cascade
);

alter table public.interviews add column if not exists app_version text not null default 'unknown';
alter table public.interviews add column if not exists agent_version text not null default 'unknown';
alter table public.interviews add column if not exists prompt_version text not null default 'unknown';
alter table public.interviews add column if not exists skill_version text not null default 'unknown';

alter table public.ai_usage_events add column if not exists event_id uuid unique;
alter table public.ai_usage_events add column if not exists attempt_no smallint not null default 1 check (attempt_no between 1 and 5);
alter table public.ai_usage_events add column if not exists total_tokens integer check (total_tokens >= 0);
alter table public.ai_usage_events add column if not exists prompt_cache_hit_tokens integer check (prompt_cache_hit_tokens >= 0);
alter table public.ai_usage_events add column if not exists prompt_cache_miss_tokens integer check (prompt_cache_miss_tokens >= 0);
alter table public.ai_usage_events add column if not exists app_version text not null default 'unknown';
alter table public.ai_usage_events add column if not exists agent_version text not null default 'unknown';
alter table public.ai_usage_events add column if not exists prompt_version text not null default 'unknown';
alter table public.ai_usage_events add column if not exists skill_version text not null default 'unknown';
alter table public.ai_usage_events add column if not exists rubric_version text not null default 'unknown';
alter table public.ai_usage_events add column if not exists http_status smallint check (http_status between 100 and 599);
alter table public.ai_usage_events add column if not exists finish_reason text check (char_length(finish_reason) <= 80);

alter table public.analytics_events enable row level security;
alter table public.acquisition_attributions enable row level security;
alter table public.feedback_responses enable row level security;

-- No client policies are created: only the backend secret key may read/write raw analytics.
revoke all on public.analytics_events from anon, authenticated;
revoke all on public.acquisition_attributions from anon, authenticated;
revoke all on public.feedback_responses from anon, authenticated;
grant all on public.analytics_events to service_role;
grant all on public.acquisition_attributions to service_role;
grant all on public.feedback_responses to service_role;

drop trigger if exists acquisition_attributions_updated_at on public.acquisition_attributions;
create trigger acquisition_attributions_updated_at before update on public.acquisition_attributions
for each row execute function public.set_updated_at();
drop trigger if exists feedback_responses_updated_at on public.feedback_responses;
create trigger feedback_responses_updated_at before update on public.feedback_responses
for each row execute function public.set_updated_at();

-- Account approval is performed in the dashboard, so record it at the database
-- boundary rather than relying on a client event that may never be sent.
create or replace function public.record_account_approval_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if old.account_status is distinct from new.account_status
     and new.account_status::text = 'approved' then
    insert into public.analytics_events (
      event_id, event_name, user_id, session_id, occurred_at, page,
      app_version, source, properties
    ) values (
      gen_random_uuid(), 'account_approved', new.user_id, gen_random_uuid(),
      timezone('utc', now()), 'database', 'unknown', 'server', '{}'::jsonb
    );
  end if;
  return new;
end;
$$;

drop trigger if exists profiles_record_account_approval on public.profiles;
create trigger profiles_record_account_approval
after update of account_status on public.profiles
for each row execute function public.record_account_approval_event();

create or replace view public.analytics_daily_activity
with (security_invoker = true) as
select
  (received_at at time zone 'Asia/Shanghai')::date as activity_date,
  count(distinct user_id) filter (where event_name = 'authenticated_session_started') as visit_dau,
  count(distinct user_id) filter (where event_name = 'interview_started') as interview_dau
from public.analytics_events
where user_id is not null
group by 1;

create or replace view public.analytics_token_by_interview
with (security_invoker = true) as
select
  interview_id,
  user_id,
  min(agent_version) as agent_version,
  min(prompt_version) as prompt_version,
  count(*) as request_count,
  count(*) filter (where outcome <> 'succeeded' or attempt_no > 1) as wasted_request_count,
  coalesce(sum(prompt_tokens), 0) as prompt_tokens,
  coalesce(sum(completion_tokens), 0) as completion_tokens,
  coalesce(sum(total_tokens), 0) as total_tokens,
  coalesce(sum(prompt_cache_hit_tokens), 0) as prompt_cache_hit_tokens,
  coalesce(sum(prompt_cache_miss_tokens), 0) as prompt_cache_miss_tokens,
  percentile_cont(0.5) within group (order by latency_ms) as latency_p50_ms,
  percentile_cont(0.95) within group (order by latency_ms) as latency_p95_ms
from public.ai_usage_events
where interview_id is not null
group by interview_id, user_id;

revoke all on public.analytics_daily_activity from anon, authenticated;
revoke all on public.analytics_token_by_interview from anon, authenticated;
grant select on public.analytics_daily_activity to service_role;
grant select on public.analytics_token_by_interview to service_role;
