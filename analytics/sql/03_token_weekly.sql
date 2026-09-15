-- 修改日期后运行，下载为 token_weekly.csv。只包含匿名 UUID 和计量字段。
with params as (
  select date '2026-09-14' as start_date, date '2026-09-21' as end_date
)
select u.interview_id, u.user_id, i.status as interview_status,
       u.operation, u.model_name, u.agent_version, u.prompt_version, u.skill_version,
       count(*) as request_count,
       count(*) filter (where u.outcome <> 'succeeded' or u.attempt_no > 1) as wasted_request_count,
       coalesce(sum(u.prompt_tokens),0) as prompt_tokens,
       coalesce(sum(u.completion_tokens),0) as completion_tokens,
       coalesce(sum(u.total_tokens),0) as total_tokens,
       coalesce(sum(u.prompt_cache_hit_tokens),0) as cache_hit_tokens,
       coalesce(sum(u.prompt_cache_miss_tokens),0) as cache_miss_tokens,
       round(percentile_cont(0.5) within group (order by u.latency_ms)::numeric,0) as latency_p50_ms,
       round(percentile_cont(0.95) within group (order by u.latency_ms)::numeric,0) as latency_p95_ms
from public.ai_usage_events u
left join public.interviews i on i.id=u.interview_id and i.user_id=u.user_id
cross join params p
where u.created_at >= p.start_date::timestamptz and u.created_at < p.end_date::timestamptz
group by u.interview_id, u.user_id, i.status, u.operation, u.model_name, u.agent_version, u.prompt_version, u.skill_version
order by u.interview_id, u.operation;
