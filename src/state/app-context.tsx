import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, PropsWithChildren, useContext, useEffect, useMemo, useState } from 'react';

import { AppState, InterviewMode, InterviewQuestion, InterviewReport, ResumeFile, TargetRole, TrainingFocus } from '@/domain/models';
import { useAuth } from '@/state/auth-context';

const STORAGE_KEY_PREFIX = '@ai-interviewer/app-state/v4';
const LEGACY_STORAGE_KEYS = ['@ai-interviewer/app-state/v2'];
const initialState: AppState = { resume: null, target: null, activeSession: null, report: null };

type ContextValue = {
  state: AppState; hydrated: boolean;
  saveResume: (resume: ResumeFile) => Promise<void>; removeResume: () => Promise<void>;
  saveTarget: (target: TargetRole) => Promise<void>;
  startDraftSession: (input: { mode: InterviewMode; focus: TrainingFocus | null; target: TargetRole; resumeId: string | null }) => Promise<void>;
  activateSession: (interviewId: string, question: InterviewQuestion, totalMainQuestions: number) => Promise<void>;
  updateAnswerDraft: (answerDraft: string) => Promise<void>; setAudioUri: (audioUri: string | null) => Promise<void>;
  applyInterviewTurn: (answer: string, nextQuestion: InterviewQuestion | null, completed: boolean) => Promise<void>;
  setSessionStatus: (status: 'active' | 'paused' | 'ended-early') => Promise<void>;
  saveReport: (report: InterviewReport) => Promise<void>; clearSession: () => Promise<void>;
};

const AppContext = createContext<ContextValue | null>(null);

export function AppProvider({ children }: PropsWithChildren) {
  const { localUserId } = useAuth();
  const storageKey = `${STORAGE_KEY_PREFIX}/${localUserId}`;
  const [state, setState] = useState<AppState>(initialState);
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    const hydrate = async () => {
      await AsyncStorage.multiRemove(LEGACY_STORAGE_KEYS);
      const raw = await AsyncStorage.getItem(storageKey);
      setState(raw ? { ...initialState, ...JSON.parse(raw) } : initialState);
    };
    void hydrate().catch(() => undefined).finally(() => setHydrated(true));
  }, [storageKey]);

  const commit = async (next: AppState) => { setState(next); await AsyncStorage.setItem(storageKey, JSON.stringify(next)); };
  const value = useMemo<ContextValue>(() => ({
    state, hydrated,
    saveResume: async (resume) => commit({ ...state, resume }),
    removeResume: async () => commit({ ...state, resume: null }),
    saveTarget: async (target) => commit({ ...state, target }),
    startDraftSession: async (input) => commit({ ...state, target: input.target, report: null, activeSession: { id: `${Date.now()}`, ...input, status: 'draft', interviewId: null, questions: [], currentIndex: 0, answers: [], totalMainQuestions: 0, answerDraft: '', audioUri: null, startedAt: null, updatedAt: new Date().toISOString() } }),
    activateSession: async (interviewId, question, totalMainQuestions) => { if (state.activeSession) await commit({ ...state, activeSession: { ...state.activeSession, interviewId, questions: [question], currentIndex: 0, totalMainQuestions, status: 'active', startedAt: new Date().toISOString(), updatedAt: new Date().toISOString() } }); },
    updateAnswerDraft: async (answerDraft) => { if (state.activeSession) await commit({ ...state, activeSession: { ...state.activeSession, answerDraft, updatedAt: new Date().toISOString() } }); },
    setAudioUri: async (audioUri) => { if (state.activeSession) await commit({ ...state, activeSession: { ...state.activeSession, audioUri, updatedAt: new Date().toISOString() } }); },
    applyInterviewTurn: async (answer, nextQuestion, completed) => {
      if (!state.activeSession) return;
      const session = state.activeSession; const question = session.questions[session.currentIndex]; if (!question) return;
      const answers = [...session.answers, { questionId: question.id, question: question.text, answer, stage: question.stage, isFollowUp: question.is_follow_up }];
      const questions = nextQuestion ? [...session.questions, nextQuestion] : session.questions;
      await commit({ ...state, activeSession: { ...session, answers, questions, currentIndex: nextQuestion ? session.currentIndex + 1 : session.currentIndex, status: completed ? 'completed' : 'active', answerDraft: '', audioUri: null, updatedAt: new Date().toISOString() } });
    },
    setSessionStatus: async (status) => { if (state.activeSession) await commit({ ...state, activeSession: { ...state.activeSession, status, updatedAt: new Date().toISOString() } }); },
    saveReport: async (report) => commit({ ...state, report }),
    clearSession: async () => commit({ ...state, activeSession: null, report: null }),
  }), [state, hydrated, storageKey]);
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() { const value = useContext(AppContext); if (!value) throw new Error('useApp must be used inside AppProvider'); return value; }
