import { Platform } from 'react-native';

import { getAccessToken } from '@/services/supabase';

export type AnalyticsEvent =
  | 'landing_viewed' | 'registration_submitted' | 'registration_created' | 'registration_failed'
  | 'account_approved' | 'authenticated_session_started' | 'sign_in_succeeded' | 'sign_in_failed'
  | 'resume_upload_started' | 'resume_upload_succeeded' | 'resume_upload_failed'
  | 'resume_parse_started' | 'resume_parse_succeeded' | 'resume_parse_failed' | 'resume_confirmed'
  | 'interview_entry_viewed' | 'interview_mode_selected' | 'interview_config_completed'
  | 'interview_start_requested' | 'interview_started' | 'interview_start_failed'
  | 'question_presented' | 'answer_submit_requested' | 'answer_accepted' | 'answer_failed'
  | 'followup_triggered' | 'interview_paused' | 'interview_resumed'
  | 'interview_ended_early' | 'interview_completed' | 'interview_abandoned'
  | 'recording_started' | 'recording_stopped' | 'transcription_succeeded' | 'transcription_failed'
  | 'report_generation_started' | 'report_generation_succeeded' | 'report_generation_failed'
  | 'report_viewed' | 'report_advice_viewed'
  | 'feedback_prompt_viewed' | 'feedback_skipped' | 'feedback_submitted';

export type AnalyticsProperties = Record<string, string | number | boolean | string[] | null>;

type PendingEvent = {
  event_id: string;
  event_name: AnalyticsEvent;
  session_id: string;
  interview_id: string | null;
  occurred_at: string;
  page: string;
  properties: AnalyticsProperties;
};

const configuredApiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, '');
const API_BASE_URL = configuredApiBaseUrl ?? (typeof window !== 'undefined' ? window.location.origin : undefined);
const SESSION_KEY = '@ai-interviewer/analytics-session';
const ACQUISITION_KEY = '@ai-interviewer/acquisition';
const pending: PendingEvent[] = [];
let sending = false;

function uuid() {
  const secureCrypto = typeof globalThis !== 'undefined' ? globalThis.crypto : undefined;
  if (secureCrypto?.randomUUID) return secureCrypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (character) => {
    const random = Math.floor(Math.random() * 16);
    const value = character === 'x' ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

function loadSessionId() {
  if (typeof window === 'undefined') return uuid();
  const existing = window.sessionStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const created = uuid();
  window.sessionStorage.setItem(SESSION_KEY, created);
  return created;
}

const sessionId = loadSessionId();

export function getAcquisitionProperties(): AnalyticsProperties {
  if (typeof window === 'undefined') return { utm_source: 'direct', utm_medium: 'none', utm_campaign: 'none', utm_content: 'none' };
  const stored = window.sessionStorage.getItem(ACQUISITION_KEY);
  if (stored) return JSON.parse(stored) as AnalyticsProperties;
  const search = new URLSearchParams(window.location.search);
  const properties = {
    utm_source: (search.get('utm_source') || 'direct').slice(0, 80),
    utm_medium: (search.get('utm_medium') || 'none').slice(0, 80),
    utm_campaign: (search.get('utm_campaign') || 'none').slice(0, 120),
    utm_content: (search.get('utm_content') || 'none').slice(0, 120),
  };
  window.sessionStorage.setItem(ACQUISITION_KEY, JSON.stringify(properties));
  return properties;
}

function currentPage() {
  return typeof window !== 'undefined' ? window.location.pathname.slice(0, 120) : 'native';
}

export function track(
  event: AnalyticsEvent,
  properties: AnalyticsProperties = {},
  interviewId: string | null = null,
) {
  pending.push({
    event_id: uuid(),
    event_name: event,
    session_id: sessionId,
    interview_id: interviewId,
    occurred_at: new Date().toISOString(),
    page: currentPage(),
    properties: { ...properties, app_surface: Platform.OS === 'web' ? 'web' : 'mobile', schema_version: 2 },
  });
  if (pending.length > 100) pending.shift();
  if (__DEV__) console.info('[analytics]', event, properties);
  void flushTelemetry();
}

export async function flushTelemetry() {
  if (sending || !API_BASE_URL || !pending.length) return;
  const token = await getAccessToken().catch(() => null);
  if (!token) return;
  sending = true;
  try {
    while (pending.length) {
      const event = pending[0];
      const response = await fetch(`${API_BASE_URL}/v1/analytics/events`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(event),
      });
      if (!response.ok) break;
      pending.shift();
    }
  } catch {
    // Analytics must never block the interview. The queue retries on the next event.
  } finally {
    sending = false;
  }
}
