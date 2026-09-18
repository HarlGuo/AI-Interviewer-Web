import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, PropsWithChildren, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { AnswerSource, AppState, InterviewMode, InterviewQuestion, InterviewReport, ResumeFile, SpeechDeliveryMetrics, TargetRole, TrainingFocus } from '@/domain/models';
import { createUuid } from '@/services/ids';
import { loadCloudResume, removeCloudResume, saveCloudResume } from '@/services/resume-cloud';
import { useAuth } from '@/state/auth-context';

const STORAGE_KEY_PREFIX = '@ai-interviewer/app-state/v4';
const LEGACY_STORAGE_KEYS = ['@ai-interviewer/app-state/v2'];
const initialState: AppState = { resume: null, target: null, activeSession: null, report: null };

type ContextValue = {
  state: AppState; hydrated: boolean;
  saveResume: (resume: ResumeFile) => Promise<void>; removeResume: () => Promise<void>;
  saveTarget: (target: TargetRole) => Promise<void>;
  startDraftSession: (input: { mode: InterviewMode; focus: TrainingFocus | null; target: TargetRole; resumeId: string | null }) => Promise<void>;
  ensureInterviewId: (interviewId: string) => Promise<void>;
  activateSession: (interviewId: string, question: InterviewQuestion, totalMainQuestions: number) => Promise<void>;
  updateAnswerDraft: (answerDraft: string) => Promise<void>; setAudioUri: (audioUri: string | null) => Promise<void>;
  applyInterviewTurn: (answer: string, source: AnswerSource, deliveryMetrics: SpeechDeliveryMetrics | null, nextQuestion: InterviewQuestion | null, completed: boolean) => Promise<void>;
  setSessionStatus: (status: 'active' | 'paused' | 'ended-early') => Promise<void>;
  saveReport: (report: InterviewReport) => Promise<void>; clearSession: () => Promise<void>;
};

const AppContext = createContext<ContextValue | null>(null);

export function AppProvider({ children }: PropsWithChildren) {
  const { cloudEnabled, localUserId, ready: authReady, user } = useAuth();
  const storageKey = `${STORAGE_KEY_PREFIX}/${localUserId}`;
  const [state, setState] = useState<AppState>(initialState);
  const [hydrated, setHydrated] = useState(false);
  const stateRef = useRef<AppState>(initialState);
  const storageKeyRef = useRef(storageKey);
  const writeQueueRef = useRef<Promise<void>>(Promise.resolve());

  useEffect(() => {
    if (!authReady) return;
    let cancelled = false;
    storageKeyRef.current = storageKey;
    setHydrated(false);
    const hydrate = async () => {
      await AsyncStorage.multiRemove(LEGACY_STORAGE_KEYS);
      const raw = await AsyncStorage.getItem(storageKey);
      let localState = initialState;
      if (raw) {
        try { localState = { ...initialState, ...JSON.parse(raw) }; }
        catch { await AsyncStorage.removeItem(storageKey); }
      }
      if (cloudEnabled && user) {
        try {
          const resume = await loadCloudResume(user.id);
          localState = { ...localState, resume };
        } catch {
          // A temporary cloud read failure must not erase a locally recoverable interview.
        }
      }
      if (cancelled) return;
      stateRef.current = localState;
      setState(localState);
      setHydrated(true);
    };
    void hydrate().catch(() => {
      if (!cancelled) {
        stateRef.current = initialState;
        setState(initialState);
        setHydrated(true);
      }
    });
    return () => { cancelled = true; };
  }, [authReady, cloudEnabled, storageKey, user?.id]);

  const commit = useCallback(async (update: (current: AppState) => AppState) => {
    const next = update(stateRef.current);
    stateRef.current = next;
    setState(next);
    const key = storageKeyRef.current;
    writeQueueRef.current = writeQueueRef.current
      .catch(() => undefined)
      .then(() => AsyncStorage.setItem(key, JSON.stringify(next)));
    await writeQueueRef.current;
  }, []);

  const value = useMemo<ContextValue>(() => ({
    state, hydrated,
    saveResume: async (resume) => {
      const savedResume = cloudEnabled && user ? await saveCloudResume(user.id, resume) : resume;
      await commit((current) => ({ ...current, resume: savedResume }));
    },
    removeResume: async () => {
      if (cloudEnabled && user) await removeCloudResume(user.id, stateRef.current.resume);
      await commit((current) => ({ ...current, resume: null }));
    },
    saveTarget: async (target) => commit((current) => ({ ...current, target })),
    startDraftSession: async (input) => commit((current) => {
      const interviewId = createUuid();
      return { ...current, target: input.target, report: null, activeSession: { id: interviewId, ...input, status: 'draft', interviewId, questions: [], currentIndex: 0, answers: [], totalMainQuestions: 0, answerDraft: '', audioUri: null, startedAt: null, updatedAt: new Date().toISOString() } };
    }),
    ensureInterviewId: async (interviewId) => commit((current) => current.activeSession && !current.activeSession.interviewId
      ? { ...current, activeSession: { ...current.activeSession, interviewId, updatedAt: new Date().toISOString() } }
      : current),
    activateSession: async (interviewId, question, totalMainQuestions) => commit((current) => current.activeSession ? { ...current, activeSession: { ...current.activeSession, interviewId, questions: [question], currentIndex: 0, totalMainQuestions, status: 'active', startedAt: new Date().toISOString(), updatedAt: new Date().toISOString() } } : current),
    updateAnswerDraft: async (answerDraft) => commit((current) => current.activeSession ? { ...current, activeSession: { ...current.activeSession, answerDraft, updatedAt: new Date().toISOString() } } : current),
    setAudioUri: async (audioUri) => commit((current) => current.activeSession ? { ...current, activeSession: { ...current.activeSession, audioUri, updatedAt: new Date().toISOString() } } : current),
    applyInterviewTurn: async (answer, source, deliveryMetrics, nextQuestion, completed) => {
      await commit((current) => {
        const session = current.activeSession;
        if (!session) return current;
        const question = session.questions[session.currentIndex];
        if (!question) return current;
        const answers = [...session.answers, { questionId: question.id, question: question.text, answer, stage: question.stage, isFollowUp: question.is_follow_up, source, deliveryMetrics }];
        const questions = nextQuestion ? [...session.questions, nextQuestion] : session.questions;
        return { ...current, activeSession: { ...session, answers, questions, currentIndex: nextQuestion ? session.currentIndex + 1 : session.currentIndex, status: completed ? 'completed' : 'active', answerDraft: '', audioUri: null, updatedAt: new Date().toISOString() } };
      });
    },
    setSessionStatus: async (status) => commit((current) => current.activeSession ? { ...current, activeSession: { ...current.activeSession, status, updatedAt: new Date().toISOString() } } : current),
    saveReport: async (report) => commit((current) => ({ ...current, report })),
    clearSession: async () => commit((current) => ({ ...current, activeSession: null, report: null })),
  }), [cloudEnabled, commit, hydrated, state, user?.id]);
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() { const value = useContext(AppContext); if (!value) throw new Error('useApp must be used inside AppProvider'); return value; }
