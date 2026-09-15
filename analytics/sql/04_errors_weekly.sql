-- 修改日期后运行，下载为 errors_weekly.csv。
with params as (
  select date '2026-09-14' as start_date, date '2026-09-21' as end_date
), client_errors as (
  select case
           when event_name like 'registration_%' or event_name like 'sign_in_%' then 'account'
           when event_name like 'resume_%' then 'resume'
           when event_name like 'interview_start_%' then 'interview_start'
           when event_name = 'answer_failed' then 'answer_analysis'
           when event_name like 'transcription_%' then 'speech'
           when event_name like 'report_generation_%' then 'report'
           else 'other'
         end as stage,
         coalesce(properties->>'error_code', 'unknown') as error_code,
         count(*) as error_count
  from public.analytics_events e cross join params p
  where e.received_at >= p.start_date::timestamptz and e.received_at < p.end_date::timestamptz
    and e.event_name in ('registration_failed','sign_in_failed','resume_upload_failed','resume_parse_failed','interview_start_failed','answer_failed','transcription_failed','report_generation_failed')
  group by 1, 2
), model_errors as (
  select operation as stage, coalesce(error_code, outcome) as error_code, count(*) as error_count
  from public.ai_usage_events u cross join params p
  where u.created_at >= p.start_date::timestamptz and u.created_at < p.end_date::timestamptz
    and u.outcome <> 'succeeded'
  group by operation, coalesce(error_code, outcome)
)
select stage, error_code, sum(error_count) as error_count
from (select * from client_errors union all select * from model_errors) errors
group by stage, error_code
order by error_count desc, stage, error_code;
