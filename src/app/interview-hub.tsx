import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { BottomNav, Button, Card, Screen } from '@/components/ui';
import { TrainingFocus } from '@/domain/models';
import { showMessage } from '@/services/dialogs';
import { useApp } from '@/state/app-context';
import { colors, radius, spacing, typography } from '@/theme/tokens';

const practices: { focus: TrainingFocus; icon: string; title: string; text: string; color: string; tint: string }[] = [
  { focus: 'self-introduction', icon: '👋', title: '自我介绍', text: '练习开场与个人亮点呈现', color: colors.primary, tint: '#EDF3FF' },
  { focus: 'resume-deep-dive', icon: '🔍', title: '简历深挖', text: '深度挖掘项目与工作经历', color: colors.success, tint: '#F0FFF4' },
  { focus: 'behavioral', icon: '⭐', title: '行为面试', text: 'STAR 法则情境题训练', color: '#FF7D00', tint: '#FFF7E6' },
  { focus: 'role-specific', icon: '💼', title: '岗位专业题', text: '针对目标职位的专业能力', color: '#7C3AED', tint: '#F5F0FF' },
];

export default function InterviewHubScreen() {
  const { state } = useApp();
  const resumeReady = state.resume?.status === 'confirmed' && state.resume.reviewStatus === 'ai_verified';
  const openSetup = (focus: TrainingFocus | null) => {
    if (!resumeReady) return router.push({ pathname: '/resume', params: focus ? { mode: 'focused', focus } : { mode: 'formal' } });
    router.push({ pathname: '/setup', params: focus ? { mode: 'focused', focus } : { mode: 'formal' } });
  };
  const openReport = () => state.report && state.activeSession ? router.push('/report') : showMessage('暂无面试报告', '完成一次模拟面试后，本次报告会显示在这里。');

  return <View style={styles.page}><Screen>
    <Text style={styles.title}>模拟面试</Text>
    {!resumeReady ? <Card tone="warning"><View style={styles.resumeRow}><View style={styles.flex}><Text style={styles.warningTitle}>⚠️ 尚未上传并确认简历</Text><Text style={styles.warningText}>完成解析和确认后，AI 才能根据你的真实经历提问</Text></View><Button label="上传" compact onPress={() => router.push('/resume')} /></View></Card> : <Card tone="success"><Text style={styles.ready}>✓ 已使用确认简历：{state.resume?.name}</Text></Card>}

    <View style={styles.formalCard}>
      <View style={styles.formalTop}><Text style={styles.recommend}>推荐</Text><Text style={styles.target}>🎯</Text></View>
      <Text style={styles.formalTitle}>正式模拟面试</Text><Text style={styles.formalBody}>完整还原真实面试流程，覆盖全部环节</Text>
      <View style={styles.tags}>{['自我介绍', '简历深挖', '行为面试', '专业题', 'AI 追问'].map((tag) => <Text key={tag} style={styles.tag}>{tag}</Text>)}</View>
      <Pressable accessibilityRole="button" onPress={() => openSetup(null)} style={styles.formalButton}><Text style={styles.formalButtonText}>开始正式模拟 →</Text></Pressable>
    </View>

    <Text style={styles.sectionTitle}>单项专项训练</Text>
    <View style={styles.grid}>{practices.map((item) => <Pressable accessibilityRole="button" key={item.focus} onPress={() => openSetup(item.focus)} style={[styles.practice, { backgroundColor: item.tint }]}><Text style={styles.practiceIcon}>{item.icon}</Text><Text style={[styles.practiceTitle, { color: item.color }]}>{item.title}</Text><Text style={styles.practiceText}>{item.text}</Text></Pressable>)}</View>

    <Card><Text style={styles.tipTitle}>📌 面试小贴士</Text>{['先上传并确认简历，AI 追问效果更精准', '找个安静环境，使用语音回答更贴近真实面试', '回答时注意量化：数据、时间、结果缺一不可'].map((tip) => <Text key={tip} style={styles.tip}>· {tip}</Text>)}</Card>
  </Screen><BottomNav active="interview" onHome={() => router.replace('/')} onInterview={() => undefined} onReport={openReport} onProfile={() => router.push('/profile')} /></View>;
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.background }, title: { ...typography.title, color: colors.primary, marginTop: spacing.xl }, resumeRow: { flexDirection: 'row', alignItems: 'center', gap: 10 }, flex: { flex: 1 }, warningTitle: { color: colors.warningText, fontWeight: '800', fontSize: 16 }, warningText: { color: colors.warningText, fontSize: 12, lineHeight: 18, marginTop: 4 }, ready: { color: colors.success, fontWeight: '700' },
  formalCard: { backgroundColor: colors.primary, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.md }, formalTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, recommend: { color: '#fff', backgroundColor: 'rgba(255,255,255,.2)', borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 5, fontWeight: '800' }, target: { fontSize: 34 }, formalTitle: { color: '#fff', fontSize: 27, fontWeight: '900' }, formalBody: { color: '#DCE7FF', fontSize: 15 }, tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, tag: { color: '#fff', backgroundColor: 'rgba(255,255,255,.18)', borderRadius: radius.pill, paddingHorizontal: 9, paddingVertical: 5, fontSize: 12 }, formalButton: { minHeight: 56, borderRadius: radius.md, backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center', marginTop: 4 }, formalButtonText: { color: colors.primary, fontSize: 17, fontWeight: '900' },
  sectionTitle: { ...typography.heading, color: colors.ink }, grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, practice: { width: '48.5%', minHeight: 145, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, padding: spacing.md, justifyContent: 'center' }, practiceIcon: { fontSize: 29 }, practiceTitle: { fontSize: 18, fontWeight: '900', marginTop: 9 }, practiceText: { color: colors.muted, fontSize: 13, lineHeight: 19, marginTop: 5 }, tipTitle: { color: colors.ink, fontWeight: '800', fontSize: 17, marginBottom: 7 }, tip: { color: colors.muted, fontSize: 13, lineHeight: 22 },
});
