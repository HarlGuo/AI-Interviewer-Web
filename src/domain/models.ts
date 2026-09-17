export type ResumeStatus = 'uploaded' | 'parsing' | 'reviewed' | 'confirmed' | 'failed';
export type ResumeSection = { title: string; content: string };
export type ResumeFile = { id: string; name: string; uri: string; size: number | null; status: ResumeStatus; uploadedAt: string; sections: ResumeSection[]; warnings: string[]; reviewStatus: 'pending' | 'ai_verified'; objectPath?: string | null };
export type TargetRole = { title: string; jd: string; savedAt: string };
export type InterviewMode = 'formal' | 'focused';
export type TrainingFocus = 'self-introduction' | 'resume-deep-dive' | 'behavioral' | 'role-specific';
export type SessionStatus = 'draft' | 'active' | 'paused' | 'completed' | 'ended-early';
export type ProjectCoverageStatus = 'covered' | 'uncovered' | 'uncertain';
export type ProjectCoverage = {
  background: ProjectCoverageStatus;
  personal_responsibility: ProjectCoverageStatus;
  technical_solution: ProjectCoverageStatus;
  problem_solving: ProjectCoverageStatus;
  result: ProjectCoverageStatus;
};
export type ProjectInterviewContext = {
  project_key: string;
  project_resume_evidence: string;
  coverage: ProjectCoverage;
  round_count: number;
  consecutive_insufficient_count: number;
  question_ids: string[];
  visited_project_evidence: string[];
};
export type InterviewQuestion = {
  id: string;
  stage: string;
  text: string;
  is_follow_up: boolean;
  main_question_index: number;
  follow_up_count: number;
  resume_evidence: string;
  project_context?: ProjectInterviewContext | null;
};
export type AnswerSource = 'text' | 'speech_transcript';
export type SpeechDeliveryMetrics = {
  duration_ms: number; voiced_duration_ms: number; pause_count: number; average_pause_ms: number;
  longest_pause_ms: number; speech_rate_cpm: number; average_volume: number; volume_variation: number; sample_count: number;
};
export type InterviewAnswer = { questionId: string; question: string; answer: string; stage: string; isFollowUp: boolean; source: AnswerSource; deliveryMetrics?: SpeechDeliveryMetrics | null };
export type InterviewSession = {
  id: string; mode: InterviewMode; focus: TrainingFocus | null; target: TargetRole; resumeId: string | null;
  status: SessionStatus; interviewId: string | null; questions: InterviewQuestion[]; currentIndex: number; answers: InterviewAnswer[]; totalMainQuestions: number;
  answerDraft: string; audioUri: string | null; startedAt: string | null; updatedAt: string;
};
export type ReportDimension = { name: string; level: number | null; score: number | null; basis: string; evidence: string[]; suggestion: string };
export type QuestionReview = { question_id: string; strengths: string[]; issues: string[]; evidence: string[]; suggestion: string };
export type InterviewReport = { overall_score: number; completion: string; summary: string; evidence_notice: string; dimensions: ReportDimension[]; question_reviews: QuestionReview[] };
export type FeedbackSubmission = {
  satisfaction_score: number;
  payment_willingness: 'willing' | 'depends_on_price' | 'unwilling' | 'prefer_not_to_say';
  tags: ('问题贴合简历' | '追问有深度' | '等待太久' | '语音体验不顺' | '问题重复')[];
  comment: string;
  completion_type: 'completed' | 'ended_early';
};
export type AppState = { resume: ResumeFile | null; target: TargetRole | null; activeSession: InterviewSession | null; report: InterviewReport | null };
