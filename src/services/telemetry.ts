export type AnalyticsEvent =
  | 'interview_entry_clicked' | 'resume_upload_started' | 'resume_upload_succeeded' | 'resume_parse_failed'
  | 'interview_config_completed' | 'interview_started' | 'question_answered' | 'followup_triggered'
  | 'interview_paused' | 'interview_completed' | 'report_viewed' | 'report_advice_viewed'
  | 'retry_interview_clicked' | 'history_report_viewed' | 'purchase_clicked';

export type AnalyticsProperties = Record<string, string | number | boolean | null>;
export type AnalyticsAdapter = { capture: (event: AnalyticsEvent, properties: AnalyticsProperties) => void | Promise<void> };

let adapter: AnalyticsAdapter | null = null;
export function configureAnalytics(next: AnalyticsAdapter | null) { adapter = next; }

export function track(event: AnalyticsEvent, properties: AnalyticsProperties = {}) {
  const safeProperties = { ...properties, app_surface: 'mobile', schema_version: 1 };
  if (__DEV__) console.info('[analytics]', event, safeProperties);
  void adapter?.capture(event, safeProperties);
}
