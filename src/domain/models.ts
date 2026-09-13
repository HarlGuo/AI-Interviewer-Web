export type ResumeStatus = 'uploaded' | 'parsing' | 'reviewed' | 'confirmed' | 'failed';
export type ResumeSection = { title: string; content: string };
export type ResumeFile = { id: string; name: string; uri: string; size: number | null; status: ResumeStatus; uploadedAt: string; sections: ResumeSection[]; warnings: string[]; reviewStatus: 'pending' | 'ai_verified'; objectPath?: string | null };
export type TargetRole = { title: string; jd: string; savedAt: string };
export type InterviewMode = 'formal' | 'focused';
export type TrainingFocus = 'self-introduction' | 'resume-deep-dive' | 'behavioral' | 'role-specific';
export type SessionStatus = 'draft' | 'active' | 'paused' | 'completed' | 'ended-early';
export type InterviewQuestion = { id: string; stage: string; text: string; is_follow_up: boolean; main_question_index: number; follow_up_count: number; resume_evidence: string };
export type InterviewAnswer = { questionId: string; question: string; answer: string; stage: string; isFollowUp: boolean };
export type InterviewSession = {
  id: string; mode: InterviewMode; focus: TrainingFocus | null; target: TargetRole; resumeId: string | null;
  status: SessionStatus; interviewId: string | null; questions: InterviewQuestion[]; currentIndex: number; answers: InterviewAnswer[]; totalMainQuestions: number;
  answerDraft: string; audioUri: string | null; startedAt: string | null; updatedAt: string;
};
export type ReportDimension = { name: string; level: number | null; score: number | null; basis: string; evidence: string[]; suggestion: string };
export type QuestionReview = { question_id: string; strengths: string[]; issues: string[]; evidence: string[]; suggestion: string };
export type InterviewReport = { overall_score: number; completion: string; summary: string; evidence_notice: string; dimensions: ReportDimension[]; question_reviews: QuestionReview[] };
export type AppState = { resume: ResumeFile | null; target: TargetRole | null; activeSession: InterviewSession | null; report: InterviewReport | null };
