import { AppState, InterviewSession } from '@/domain/models';

export function beijingDate(now = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}

export function isResumableSession(session: InterviewSession | null | undefined): session is InterviewSession {
  if (!session) return false;
  return session.status === 'draft' || session.status === 'active' || session.status === 'paused';
}

export function isQuotaUsedToday(state: Pick<AppState, 'quotaConsumedOn' | 'activeSession'>): boolean {
  const today = beijingDate();
  if (state.quotaConsumedOn === today) return true;
  const session = state.activeSession;
  if (!session || (session.status !== 'completed' && session.status !== 'ended-early')) return false;
  return beijingDate(new Date(session.updatedAt)) === today;
}
