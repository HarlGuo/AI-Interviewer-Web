alter table public.ai_usage_events
  drop constraint if exists ai_usage_events_operation_check;

alter table public.ai_usage_events
  add constraint ai_usage_events_operation_check
  check (operation in ('resume_review', 'skill_selection', 'question_generation', 'answer_analysis', 'report_generation'));
