-- Supabase SQL Editor：只修改 params 的日期，然后运行并下载为 funnel_weekly.csv。
-- 结束日期不包含当天，例如统计 9/14 至 9/20，应填 end_date = '2026-09-21'。
with params as (
  select date '2026-09-14' as start_date, date '2026-09-21' as end_date
), cohort as (
  select u.id as user_id, u.created_at,
         coalesce(a.utm_source, 'direct') as utm_source,
         coalesce(a.utm_campaign, 'none') as utm_campaign,
         coalesce(a.utm_content, 'none') as utm_content
  from auth.users u
  left join public.acquisition_attributions a on a.user_id = u.id
  cross join params p
  where u.created_at >= p.start_date::timestamptz
    and u.created_at < p.end_date::timestamptz
), event_flags as (
  select c.*,
         exists(select 1 from public.analytics_events e where e.user_id=c.user_id and e.event_name='landing_viewed') as landed,
         exists(select 1 from public.profiles p where p.user_id=c.user_id and p.account_status::text='approved') as approved,
         exists(select 1 from public.analytics_events e where e.user_id=c.user_id and e.event_name='resume_confirmed') as resume_confirmed,
         exists(select 1 from public.interviews i where i.user_id=c.user_id and i.started_at is not null) as started,
         exists(select 1 from public.interviews i where i.user_id=c.user_id and i.status='completed') as completed,
         exists(select 1 from public.interview_reports r where r.user_id=c.user_id and r.status='completed') as report_generated
  from cohort c
)
select utm_source, utm_campaign, utm_content,
       count(*) as registered_users,
       count(*) filter (where landed) as attributable_landing_users,
       count(*) filter (where approved) as approved_users,
       count(*) filter (where resume_confirmed) as resume_confirmed_users,
       count(*) filter (where started) as started_users,
       count(*) filter (where completed) as completed_users,
       count(*) filter (where report_generated) as report_users,
       round(count(*) filter (where started)::numeric / nullif(count(*),0), 4) as registration_to_start_rate,
       round(count(*) filter (where completed)::numeric / nullif(count(*) filter (where started),0), 4) as completion_rate
from event_flags
group by utm_source, utm_campaign, utm_content
order by registered_users desc, utm_source, utm_content;
