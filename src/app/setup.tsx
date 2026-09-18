import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput } from 'react-native';
import { Button, Card, Screen } from '@/components/ui';
import { InterviewMode, TrainingFocus } from '@/domain/models';
import { track } from '@/services/telemetry';
import { showMessage } from '@/services/dialogs';
import { useApp } from '@/state/app-context';
import { isQuotaUsedToday, isResumableSession } from '@/state/session-recovery';
import { colors, radius, spacing, typography } from '@/theme/tokens';

const focuses: { value: TrainingFocus; label: string; caption: string }[] = [
  { value: 'self-introduction', label: '自我介绍', caption: '开场与个人亮点' }, { value: 'resume-deep-dive', label: '简历深挖', caption: '项目与工作经历' },
  { value: 'behavioral', label: '行为面试', caption: 'STAR 情境题' }, { value: 'role-specific', label: '岗位专业题', caption: '目标岗位能力' },
];

export default function SetupScreen() {
  const params = useLocalSearchParams<{ mode?: string; focus?: string }>();
  const { state, startDraftSession } = useApp();
  const initialMode: InterviewMode = params.mode === 'focused' ? 'focused' : 'formal';
  const initialFocus = focuses.some((item) => item.value === params.focus) ? params.focus as TrainingFocus : 'resume-deep-dive';
  const [title, setTitle] = useState(state.target?.title ?? ''); const [jd, setJd] = useState(state.target?.jd ?? '');
  const mode = initialMode; const focus = initialFocus; const [showJd, setShowJd] = useState(Boolean(state.target?.jd));

  const continueToInterview = async () => {
    if (isResumableSession(state.activeSession)) {
      router.replace('/interview');
      return;
    }
    if (isQuotaUsedToday(state)) return showMessage('今日面试次数已用完', '每个账号每天只能完成一次模拟面试，请明天再来。');
    if (!state.resume || state.resume.status !== 'confirmed' || state.resume.reviewStatus !== 'ai_verified') return showMessage('请先确认简历', '完成 PDF 解析、AI 复核和用户确认后才能开始。');
    if (!title.trim()) return showMessage('请填写目标职位', '目标职位用于生成岗位相关问题。');
    const target = { title: title.trim(), jd: jd.trim(), savedAt: new Date().toISOString() };
    await startDraftSession({ mode, focus: mode === 'focused' ? focus : null, target, resumeId: state.resume.id });
    track('interview_config_completed', { mode, focus: mode === 'focused' ? focus : null, has_jd: Boolean(jd.trim()) }); router.push('/interview');
  };

  return <Screen keyboard>
    <Text style={styles.heading}>已选择的面试类型</Text><Card tone="blue"><Text style={styles.selectedTitle}>{mode === 'formal' ? '正式模拟面试' : focuses.find((item) => item.value === focus)?.label}</Text><Text style={styles.formalText}>{mode === 'formal' ? '依次覆盖自我介绍、简历深挖、行为面试、岗位专业题和结束反问。' : focuses.find((item) => item.value === focus)?.caption}</Text><Pressable onPress={() => router.back()}><Text style={styles.changeType}>更换面试类型</Text></Pressable></Card>
    <Text style={styles.label}>目标职位 <Text style={styles.required}>* 必填</Text></Text><TextInput value={title} onChangeText={setTitle} style={styles.input} placeholder="例：产品经理、前端开发、数据分析师" placeholderTextColor={colors.placeholder} />
    <Pressable onPress={() => setShowJd(!showJd)}><Text style={styles.jdToggle}>{showJd ? '▾' : '▸'} 粘贴岗位 JD（可选）</Text></Pressable>
    {showJd ? <TextInput value={jd} onChangeText={setJd} multiline textAlignVertical="top" style={[styles.input, styles.jd]} placeholder="粘贴真实岗位描述，AI 将据此生成更相关的问题" placeholderTextColor={colors.placeholder} /> : null}
    <Button label="开始面试" disabled={!title.trim()} onPress={continueToInterview} />
    <Text style={styles.footnote}>开始后将生成第一道个性化问题。麦克风权限只会在你点击录音时申请。</Text>
  </Screen>;
}

const styles = StyleSheet.create({
  heading: { ...typography.heading, color: colors.ink, marginTop: spacing.md }, selectedTitle: { color: colors.primary, fontWeight: '900', fontSize: 18 }, formalText: { color: colors.primary, lineHeight: 21, marginTop: 5 }, changeType: { color: colors.primary, fontWeight: '800', textDecorationLine: 'underline', marginTop: 12 },
  label: { color: colors.ink, fontSize: 17, fontWeight: '800', marginTop: spacing.md }, required: { color: colors.danger, fontSize: 13 }, input: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: 15, color: colors.ink, fontSize: 16 }, jd: { minHeight: 150 }, jdToggle: { color: colors.primary, fontWeight: '800', fontSize: 16, paddingVertical: 8 }, footnote: { color: colors.muted, fontSize: 12, lineHeight: 18, textAlign: 'center' },
});
