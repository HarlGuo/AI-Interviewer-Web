-- 修改日期后运行，下载为 engagement_weekly.csv。
-- 留存以首次成功开始面试为 Day 0；未满观察窗口的 cohort 不进入相应分母。
with params as (
  select date '2026-09-14' as start_date, date '2026-09-21' as end_date
), days as (
  select generate_series(p.start_date, p.end_date - 1, interval '1 day')::date as day from params p
), daily as (
  select d.day,
    (select count(distinct e.user_id) from public.analytics_events e where e.event_name='authenticated_session_started' and (e.received_at at time zone 'Asia/Shanghai')::date=d.day) as visit_dau,
    (select count(distinct i.user_id) from public.interviews i where (i.started_at at time zone 'Asia/Shanghai')::date=d.day) as interview_dau
  from days d
), first_use as (
  select user_id, min((started_at at time zone 'Asia/Shanghai')::date) as day0
  from public.interviews where started_at is not null group by user_id
), mature as (
  select f.* from first_use f cross join params p where f.day0 >= p.start_date and f.day0 < p.end_date
), retention as (
  select
    count(*) filter (where day0 + 1 <= current_date) as d1_eligible,
    count(*) filter (where day0 + 1 <= current_date and exists(select 1 from public.interviews i where i.user_id=m.user_id and (i.started_at at time zone 'Asia/Shanghai')::date=m.day0+1)) as d1_returned,
    count(*) filter (where day0 + 7 <= current_date) as d7_eligible,
    count(*) filter (where day0 + 7 <= current_date and exists(select 1 from public.interviews i where i.user_id=m.user_id and (i.started_at at time zone 'Asia/Shanghai')::date between m.day0+1 and m.day0+7)) as d7_window_returned,
    count(*) filter (where day0 + 7 <= current_date and exists(select 1 from public.interviews i where i.user_id=m.user_id and (i.started_at at time zone 'Asia/Shanghai')::date=m.day0+7)) as exact_d7_returned
  from mature m
), feedback as (
  select count(*) as responses,
         round(avg(satisfaction_score), 2) as avg_satisfaction,
         count(*) filter (where satisfaction_score >= 4) as satisfied,
         count(*) filter (where payment_willingness in ('willing','depends_on_price')) as payment_positive
  from public.feedback_responses f cross join params p
  where f.submitted_at >= p.start_date::timestamptz and f.submitted_at < p.end_date::timestamptz
)
select 'daily' as section, day::text as period, 'visit_dau' as metric, visit_dau::numeric as value, null::numeric as denominator, null::numeric as rate from daily
union all select 'daily', day::text, 'interview_dau', interview_dau, null, null from daily
union all select 'retention', 'week', 'd1_interview_retention', d1_returned, d1_eligible, round(d1_returned::numeric/nullif(d1_eligible,0),4) from retention
union all select 'retention', 'week', 'd7_reuse_window', d7_window_returned, d7_eligible, round(d7_window_returned::numeric/nullif(d7_eligible,0),4) from retention
union all select 'retention', 'week', 'exact_d7_retention', exact_d7_returned, d7_eligible, round(exact_d7_returned::numeric/nullif(d7_eligible,0),4) from retention
union all select 'feedback', 'week', 'responses', responses, null, null from feedback
union all select 'feedback', 'week', 'average_satisfaction', avg_satisfaction, responses, null from feedback
union all select 'feedback', 'week', 'satisfied_share', satisfied, responses, round(satisfied::numeric/nullif(responses,0),4) from feedback
union all select 'feedback', 'week', 'payment_interest_share', payment_positive, responses, round(payment_positive::numeric/nullif(responses,0),4) from feedback
order by section, period, metric;
