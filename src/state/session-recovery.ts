import { InterviewSession } from '@/domain/models';

export function isResumableSession(session: InterviewSession | null | undefined): session is InterviewSession {
  if (!session) return false;
  return session.status === 'draft' || session.status === 'active' || session.status === 'paused';
}
