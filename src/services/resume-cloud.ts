import { ResumeFile, ResumeSection, ResumeStatus } from '@/domain/models';
import { supabase } from '@/services/supabase';

const BUCKET = 'resumes';
const SIGNED_URL_SECONDS = 60 * 60;

export type ResumeUploadSource = {
  webFile?: File;
};

function cloudErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) return error.message;
  if (error && typeof error === 'object') {
    const candidate = error as { message?: unknown; error?: unknown };
    if (typeof candidate.message === 'string' && candidate.message.trim()) return candidate.message;
    if (typeof candidate.error === 'string' && candidate.error.trim()) return candidate.error;
  }
  return fallback;
}

function resumeSaveErrorMessage(error: unknown): string {
  const message = cloudErrorMessage(error, '简历信息保存失败，请稍后重试。');
  if (message.includes('duplicate key value') || message.includes('resumes_object_path_key')) {
    return '检测到旧简历记录，暂时无法完成替换，请重新选择文件后重试。';
  }
  return message;
}

type ResumeRow = {
  id: string;
  file_name: string;
  object_path: string | null;
  file_size_bytes: number | null;
  status: ResumeStatus;
  review_status: 'pending' | 'ai_verified';
  sections: unknown;
  warnings: unknown;
  created_at: string;
};

function parseSections(value: unknown): ResumeSection[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is ResumeSection => Boolean(
    item && typeof item === 'object'
      && typeof (item as ResumeSection).title === 'string'
      && typeof (item as ResumeSection).content === 'string',
  ));
}

function parseWarnings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

async function rowToResume(row: ResumeRow): Promise<ResumeFile> {
  let uri = '';
  if (row.object_path && supabase) {
    const { data, error } = await supabase.storage.from(BUCKET).createSignedUrl(row.object_path, SIGNED_URL_SECONDS);
    if (error) throw error;
    uri = data.signedUrl;
  }
  return {
    id: row.id,
    name: row.file_name,
    uri,
    size: row.file_size_bytes,
    status: row.status,
    uploadedAt: row.created_at,
    sections: parseSections(row.sections),
    warnings: parseWarnings(row.warnings),
    reviewStatus: row.review_status,
    objectPath: row.object_path,
  };
}

export async function loadCloudResume(userId: string): Promise<ResumeFile | null> {
  if (!supabase) return null;
  const { data, error } = await supabase
    .from('resumes')
    .select('id,file_name,object_path,file_size_bytes,status,review_status,sections,warnings,created_at')
    .eq('user_id', userId)
    .is('deleted_at', null)
    .order('updated_at', { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) throw error;
  return data ? rowToResume(data as ResumeRow) : null;
}

export async function saveCloudResume(userId: string, resume: ResumeFile, source?: ResumeUploadSource): Promise<ResumeFile> {
  if (!supabase) return resume;
  const { data: existing, error: existingError } = await supabase
    .from('resumes')
    .select('id,object_path,created_at')
    .eq('user_id', userId)
    .is('deleted_at', null)
    .order('updated_at', { ascending: false })
    .limit(1)
    .maybeSingle();
  if (existingError) throw new Error(resumeSaveErrorMessage(existingError));

  const replacingFile = !resume.objectPath;
  const localObjectPath = resume.objectPath?.startsWith(`${userId}/`) ? resume.objectPath : null;
  const objectPath = existing?.object_path
    ?? localObjectPath
    ?? (existing ? `${userId}/${existing.id}.pdf` : `${userId}/current.pdf`);
  if (replacingFile) {
    let uploadBody: File | ArrayBuffer;
    if (source?.webFile) {
      uploadBody = source.webFile;
    } else {
      const response = await fetch(resume.uri);
      if (!response.ok) throw new Error('无法读取所选 PDF，请重新选择。');
      uploadBody = await response.arrayBuffer();
    }
    const { error: uploadError } = await supabase.storage.from(BUCKET).upload(objectPath, uploadBody, {
      contentType: 'application/pdf',
      upsert: true,
    });
    if (uploadError) throw new Error(cloudErrorMessage(uploadError, 'PDF 上传到云端失败，请稍后重试。'));
  }

  const values = {
    user_id: userId,
    file_name: resume.name,
    object_path: objectPath,
    file_size_bytes: resume.size,
    status: resume.status,
    review_status: resume.reviewStatus,
    sections: resume.sections,
    warnings: resume.warnings,
    confirmed_at: resume.status === 'confirmed' ? new Date().toISOString() : null,
    deleted_at: null,
  };
  const query = existing
    ? supabase.from('resumes').update(values).eq('id', existing.id).eq('user_id', userId)
    // A soft-deleted resume can still own this globally unique object_path.
    // Upsert revives that row and also makes concurrent first uploads idempotent.
    : supabase.from('resumes').upsert(values, { onConflict: 'object_path' });
  const { data, error } = await query
    .select('id,file_name,object_path,file_size_bytes,status,review_status,sections,warnings,created_at')
    .single();
  if (error) throw new Error(resumeSaveErrorMessage(error));
  return rowToResume(data as ResumeRow);
}

export async function removeCloudResume(userId: string, resume: ResumeFile | null): Promise<void> {
  if (!supabase || !resume) return;
  if (resume.objectPath) {
    const { error: storageError } = await supabase.storage.from(BUCKET).remove([resume.objectPath]);
    if (storageError) throw storageError;
  }
  const { error } = await supabase
    .from('resumes')
    .update({ status: 'deleted', deleted_at: new Date().toISOString() })
    .eq('id', resume.id)
    .eq('user_id', userId);
  if (error) throw error;
}
