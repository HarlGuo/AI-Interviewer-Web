import * as DocumentPicker from 'expo-document-picker';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { Button, Card, Screen } from '@/components/ui';
import { ApiNotConfiguredError, resumeGateway } from '@/services/gateways';
import { showMessage } from '@/services/dialogs';
import { track } from '@/services/telemetry';
import { useApp } from '@/state/app-context';
import { colors, radius, spacing, typography } from '@/theme/tokens';

const MAX_BYTES = 10 * 1024 * 1024;

export default function ResumeScreen() {
  const params = useLocalSearchParams<{ mode?: string; focus?: string }>();
  const { state, saveResume, removeResume } = useApp();
  const [busy, setBusy] = useState(false); const [agreed, setAgreed] = useState(false); const [error, setError] = useState(''); const [expanded, setExpanded] = useState<string[]>([]);

  const pickResume = async () => {
    if (!agreed && !state.resume) return setError('请先确认你已阅读简历使用说明。');
    setError(''); track('resume_upload_started');
    const result = await DocumentPicker.getDocumentAsync({ type: 'application/pdf', multiple: false, copyToCacheDirectory: true });
    if (result.canceled) return;
    const asset = result.assets[0];
    if (!asset.name.toLowerCase().endsWith('.pdf') && asset.mimeType !== 'application/pdf') return setError('文件格式不支持，请重新选择 PDF。');
    if (typeof asset.size === 'number' && asset.size > MAX_BYTES) return setError('文件超过 10 MB，请压缩后重新上传。');
    await saveResume({ id: `${Date.now()}`, name: asset.name, uri: asset.uri, size: asset.size ?? null, status: 'uploaded', uploadedAt: new Date().toISOString(), sections: [], warnings: [], reviewStatus: 'pending' });
    track('resume_upload_succeeded', { size_bytes: asset.size ?? 0 });
  };

  const parse = async () => {
    if (!state.resume || busy) return; setBusy(true); setError('');
    await saveResume({ ...state.resume, status: 'parsing' });
    try {
      const parsed = await resumeGateway.parse(state.resume);
      await saveResume({ ...state.resume, status: 'reviewed', sections: parsed.sections, warnings: [...parsed.warnings, ...parsed.review_issues], reviewStatus: parsed.review_status === 'ai_verified' ? 'ai_verified' : 'pending' });
      setExpanded(parsed.sections.slice(0, 1).map((item) => item.title));
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : '请稍后重试。';
      track('resume_parse_failed', { reason: cause instanceof ApiNotConfiguredError ? 'not_configured' : 'request_failed' });
      await saveResume({ ...state.resume, status: 'failed' }); setError(message);
    } finally { setBusy(false); }
  };

  const confirm = async () => {
    if (!state.resume || state.resume.reviewStatus !== 'ai_verified') return showMessage('尚不能确认', 'AI 复核和完整性校验通过后才能确认。');
    await saveResume({ ...state.resume, status: 'confirmed' });
  };
  const goSetup = () => router.push({ pathname: '/setup', params: { mode: params.mode ?? 'formal', ...(params.focus ? { focus: params.focus } : {}) } });
  const toggle = (title: string) => setExpanded((items) => items.includes(title) ? items.filter((item) => item !== title) : [...items, title]);
  const resume = state.resume;

  return <Screen>
    <Card tone="blue"><Text style={styles.privacyTitle}>🔒 简历隐私说明</Text><Text style={styles.privacyText}>简历仅用于生成本人的面试问题，不加入公共数据库。模型复核前会脱敏联系方式；仍建议上传前移除不必要的敏感信息。</Text></Card>
    {!resume ? <>
      <Pressable onPress={() => setAgreed(!agreed)} style={styles.agreement}><View style={[styles.checkbox, agreed && styles.checkboxOn]}><Text style={styles.check}>{agreed ? '✓' : ''}</Text></View><Text style={styles.agreementText}>我已阅读简历使用说明，并授权用于本次模拟面试</Text></Pressable>
      <Pressable accessibilityRole="button" onPress={pickResume} style={styles.dropzone}><Text style={styles.fileIcon}>📄</Text><Text style={styles.uploadTitle}>点击选择 PDF 简历</Text><Text style={styles.meta}>仅支持 PDF · 最大 10 MB</Text></Pressable>
    </> : <Card tone={resume.status === 'confirmed' ? 'success' : resume.status === 'failed' ? 'warning' : 'default'}><View style={styles.fileRow}><Text style={styles.fileIconSmall}>📄</Text><View style={styles.flex}><Text style={styles.fileName}>{resume.name}</Text><Text style={styles.meta}>{resume.size ? `${(resume.size / 1024 / 1024).toFixed(2)} MB` : '大小未知'} · PDF</Text></View></View>
      <Text style={styles.status}>{resume.status === 'confirmed' ? '✓ 已确认，可用于面试' : resume.status === 'reviewed' ? 'AI 复核完成，请检查内容' : resume.status === 'parsing' ? '正在提取、AI 复核和校验…' : resume.status === 'failed' ? '解析失败，可重试或替换' : '文件已上传，等待解析'}</Text>
      <View style={styles.actions}><Button label="替换文件" variant="secondary" compact onPress={pickResume} /><Button label="删除" variant="ghost" compact onPress={removeResume} /></View>
    </Card>}
    {error ? <Card tone="warning"><Text style={styles.errorTitle}>处理失败</Text><Text style={styles.errorText}>{error}</Text></Card> : null}
    {resume && ['uploaded', 'failed'].includes(resume.status) ? <Button label={busy ? '正在解析并复核…' : resume.status === 'failed' ? '重新解析' : '解析并使用 AI 复核'} disabled={busy} onPress={parse} /> : null}
    {busy ? <View style={styles.busy}><ActivityIndicator color={colors.primary} /><Text style={styles.busyText}>正在提取文本、脱敏、AI 分类并校验完整性，请勿重复点击</Text></View> : null}
    {resume?.sections.map((section) => <View key={section.title} style={styles.section}><Pressable onPress={() => toggle(section.title)} style={styles.sectionHeader}><Text style={styles.sectionTitle}>{section.title}</Text><Text style={styles.chevron}>{expanded.includes(section.title) ? '▾' : '▸'}</Text></Pressable>{expanded.includes(section.title) ? <Text selectable style={styles.sectionBody}>{section.content}</Text> : null}</View>)}
    {resume?.warnings.map((warning, index) => <Text key={`${warning}-${index}`} style={styles.warning}>• {warning}</Text>)}
    {resume?.status === 'reviewed' ? <><Card tone="blue"><Text style={styles.confirmText}>请逐项检查。AI 验证只表示结构完整性检查通过，不保证简历陈述真实或绝对零错误。</Text></Card><Button label="我已检查，确认这份简历" onPress={confirm} /></> : null}
    {resume?.status === 'confirmed' ? <Button label="进入面试设置" onPress={goSetup} /> : null}
  </Screen>;
}

const styles = StyleSheet.create({
  privacyTitle: { color: colors.primary, fontWeight: '800' }, privacyText: { color: colors.muted, fontSize: 13, lineHeight: 20, marginTop: 6 }, agreement: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' }, checkbox: { width: 22, height: 22, borderRadius: 6, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }, checkboxOn: { backgroundColor: colors.primary, borderColor: colors.primary }, check: { color: '#fff', fontWeight: '800' }, agreementText: { color: colors.muted, flex: 1, lineHeight: 21 },
  dropzone: { borderWidth: 2, borderStyle: 'dashed', borderColor: colors.primary, borderRadius: radius.lg, paddingVertical: 48, alignItems: 'center', backgroundColor: colors.surface }, fileIcon: { fontSize: 50 }, uploadTitle: { ...typography.heading, color: colors.ink, marginTop: 14 }, meta: { color: colors.muted, fontSize: 13, marginTop: 4 }, fileRow: { flexDirection: 'row', gap: 12, alignItems: 'center' }, fileIconSmall: { fontSize: 30 }, flex: { flex: 1 }, fileName: { color: colors.ink, fontWeight: '800', fontSize: 16 }, status: { color: colors.primary, fontWeight: '700', marginTop: 14 }, actions: { flexDirection: 'row', gap: 8, marginTop: 14 },
  errorTitle: { color: colors.warningText, fontWeight: '800' }, errorText: { color: colors.warningText, marginTop: 5, lineHeight: 20 }, busy: { alignItems: 'center', gap: 9, padding: spacing.md }, busyText: { color: colors.muted, textAlign: 'center', fontSize: 13 }, section: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, backgroundColor: colors.surface, overflow: 'hidden' }, sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', padding: spacing.md, backgroundColor: colors.surfaceMuted }, sectionTitle: { color: colors.ink, fontWeight: '800' }, chevron: { color: colors.muted }, sectionBody: { color: colors.ink, fontSize: 14, lineHeight: 22, padding: spacing.md }, warning: { color: colors.warningText, fontSize: 12, lineHeight: 18 }, confirmText: { color: colors.primary, lineHeight: 21 },
});
