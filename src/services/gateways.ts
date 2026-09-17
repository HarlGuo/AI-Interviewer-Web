import { AnswerSource, FeedbackSubmission, InterviewQuestion, InterviewReport, InterviewSession, ResumeFile, ResumeSection, SpeechDeliveryMetrics } from '@/domain/models';
import { Platform } from 'react-native';
import { getAccessToken } from '@/services/supabase';

const configuredApiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, '');
const API_BASE_URL = configuredApiBaseUrl
  ?? (typeof window !== 'undefined' ? window.location.origin : undefined);
const REQUEST_TIMEOUT_MS = 65_000;
const INTERVIEW_TURN_TIMEOUT_MS = 130_000;
const REPORT_TIMEOUT_MS = 210_000;

export class ApiNotConfiguredError extends Error {
  constructor(public capability: 'backend') { super(`${capability} is not configured`); }
}
function apiUrl(path: string) { if (!API_BASE_URL) throw new ApiNotConfiguredError('backend'); return `${API_BASE_URL}${path}`; }
async function request(input: string, init: RequestInit, timeoutMs = REQUEST_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const token = await getAccessToken();
    const headers = new Headers(init.headers);
    if (token) headers.set('Authorization', `Bearer ${token}`);
    return await fetch(input, { ...init, headers, signal: controller.signal });
  }
  catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw new Error('请求超时，请确认网络和后端服务后重试。');
    throw new Error('无法连接后端。真机调试时请使用电脑的局域网 IP，不能使用 127.0.0.1。');
  } finally { clearTimeout(timer); }
}
async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail)
      ? body.detail.map((item: { msg?: string }) => item.msg ?? '请求格式错误').join('；')
      : body.detail;
    throw new Error(typeof detail === 'string' ? detail : `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const resumeGateway = {
  async parse(resume: ResumeFile): Promise<{ sections: ResumeSection[]; warnings: string[]; review_status: 'rule_only' | 'ai_verified'; review_issues: string[] }> {
    const form = new FormData();
    if (Platform.OS === 'web') {
      const fileResponse = await fetch(resume.uri);
      if (!fileResponse.ok) throw new Error('浏览器无法读取所选 PDF，请重新选择文件。');
      const blob = await fileResponse.blob();
      form.append('file', blob, resume.name);
    } else {
      form.append('file', { uri: resume.uri, name: resume.name, type: 'application/pdf' } as unknown as Blob);
    }
    return parseResponse(await request(apiUrl('/v1/resumes/parse'), { method: 'POST', body: form }));
  },
};
export const interviewGateway = {
  async start(session: InterviewSession, resume: ResumeFile): Promise<{ interview_id: string; question: InterviewQuestion; total_main_questions: number; source: string }> {
    return parseResponse(await request(apiUrl('/v1/interviews'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resume_id: resume.id, target_role: session.target.title, job_description: session.target.jd, mode: session.mode, focus: session.focus, resume_sections: resume.sections, resume_review_status: resume.reviewStatus }) }));
  },
  async turn(session: InterviewSession, resume: ResumeFile, answer: string, source: AnswerSource, deliveryMetrics: SpeechDeliveryMetrics | null): Promise<{ next_question: InterviewQuestion | null; completed: boolean; decision_reason: string; weakness: string; total_main_questions: number }> {
    const current = session.questions[session.currentIndex];
    const answers = [...session.answers.map((item) => ({ question_id: item.questionId, question: item.question, answer: item.answer, stage: item.stage, is_follow_up: item.isFollowUp, source: item.source ?? 'text', delivery_metrics: item.deliveryMetrics ?? null })), { question_id: current.id, question: current.text, answer, stage: current.stage, is_follow_up: current.is_follow_up, source, delivery_metrics: deliveryMetrics }];
    const result = await parseResponse<{ next_question: InterviewQuestion | null; completed: boolean; decision_reason: string; weakness: string; total_main_questions: number }>(await request(apiUrl('/v1/interviews/turn'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ interview_id: session.interviewId, target_role: session.target.title, job_description: session.target.jd, mode: session.mode, focus: session.focus, resume_sections: resume.sections, resume_review_status: resume.reviewStatus, current_question: current, answers }) }, INTERVIEW_TURN_TIMEOUT_MS));
    if (!result.completed && !result.next_question) throw new Error('后端未返回下一道问题，请重新提交当前回答。');
    return result;
  },
  async report(session: InterviewSession): Promise<InterviewReport> {
    return parseResponse(await request(apiUrl('/v1/reports'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ interview_id: session.interviewId, target_role: session.target.title, mode: session.mode, completed: session.status === 'completed', answers: session.answers.map((item) => ({ question_id: item.questionId, question: item.question, answer: item.answer, delivery_metrics: item.deliveryMetrics ?? null })) }) }, REPORT_TIMEOUT_MS));
  },
  async updateStatus(interviewId: string, status: 'active' | 'paused' | 'ended-early') {
    return parseResponse<{ saved: boolean }>(await request(apiUrl(`/v1/interviews/${interviewId}/status`), { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) }));
  },
  async feedback(interviewId: string, feedback: FeedbackSubmission) {
    return parseResponse<{ saved: boolean }>(await request(apiUrl(`/v1/interviews/${interviewId}/feedback`), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(feedback) }));
  },
};
