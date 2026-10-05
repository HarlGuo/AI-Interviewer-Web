import { InterviewReport, InterviewReportRecord, InterviewMode, TrainingFocus } from '@/domain/models';
import { supabase } from '@/services/supabase';

type ReportRow = { interview_id: string; report_data: unknown; generated_at: string | null };
type InterviewRow = {
  id: string; mode: InterviewMode; focus: TrainingFocus | null; status: string;
  target_title_snapshot: string; job_description_snapshot: string; started_at: string | null;
  completed_at: string | null; updated_at: string;
};

function isReport(value: unknown): value is InterviewReport {
  if (!value || typeof value !== 'object') return false;
  const report = value as Partial<InterviewReport>;
  return typeof report.overall_score === 'number'
    && typeof report.completion === 'string'
    && typeof report.summary === 'string'
    && Array.isArray(report.dimensions)
    && Array.isArray(report.question_reviews);
}

export async function loadCloudReportHistory(): Promise<InterviewReportRecord[]> {
  if (!supabase) return [];
  const { data: reportRows, error: reportError } = await supabase
    .from('interview_reports')
    .select('interview_id, report_data, generated_at')
    .eq('status', 'completed')
    .order('generated_at', { ascending: false })
    .limit(20);
  if (reportError) throw reportError;

  const reports = (reportRows ?? []) as ReportRow[];
  const interviewIds = reports.map((row) => row.interview_id);
  if (!interviewIds.length) return [];
  const { data: interviewRows, error: interviewError } = await supabase
    .from('interviews')
    .select('id, mode, focus, status, target_title_snapshot, job_description_snapshot, started_at, completed_at, updated_at')
    .in('id', interviewIds);
  if (interviewError) throw interviewError;

  const interviews = new Map(((interviewRows ?? []) as InterviewRow[]).map((row) => [row.id, row]));
  return reports.flatMap((row) => {
    const interview = interviews.get(row.interview_id);
    if (!interview || !isReport(row.report_data)) return [];
    const completedAt = row.generated_at ?? interview.completed_at ?? interview.updated_at;
    return [{
      id: row.interview_id,
      interviewId: row.interview_id,
      target: { title: interview.target_title_snapshot, jd: interview.job_description_snapshot, savedAt: interview.started_at ?? completedAt },
      mode: interview.mode,
      focus: interview.focus,
      status: interview.status === 'ended-early' ? 'ended-early' as const : 'completed' as const,
      startedAt: interview.started_at,
      completedAt,
      report: row.report_data,
    }];
  });
}
