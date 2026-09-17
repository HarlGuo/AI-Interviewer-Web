alter table public.interview_answers
  add column if not exists delivery_metrics jsonb not null default '{}'::jsonb;

comment on column public.interview_answers.delivery_metrics is
  '客户端从同一次语音回答中计算的语速、停顿和收音稳定性指标；不保存原始录音。';
