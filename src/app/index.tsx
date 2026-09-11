import { router } from 'expo-router';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { BottomNav, Button, Card, Screen } from '@/components/ui';
import { TrainingFocus } from '@/domain/models';
import { track } from '@/services/telemetry';
import { showMessage } from '@/services/dialogs';
import { useApp } from '@/state/app-context';
import { colors, radius, spacing, typography } from '@/theme/tokens';

const practices: { focus: TrainingFocus; icon: string; title: string; text: string; color: string; tint: string }[] = [
  { focus: 'self-introduction', icon: '👋', title: '自我介绍', text: '练习开场与个人亮点呈现', color: colors.primary, tint: '#EDF3FF' },
  { focus: 'resume-deep-dive', icon: '🔍', title: '简历深挖', text: '深度挖掘项目与工作经历', color: colors.success, tint: '#F0FFF4' },
  { focus: 'behavioral', icon: '⭐', title: '行为面试', text: 'STAR 法则情境题训练', color: '#FF7D00', tint: '#FFF7E6' },
  { focus: 'role-specific', icon: '💼', title: '岗位专业题', text: '针对目标职位的专业能力', color: '#7C3AED', tint: '#F5F0FF' },
];

export default function HomeScreen() {
  const { hydrated, state } = useApp();
  if (!hydrated) return <View style={styles.loading}><ActivityIndicator color={colors.primary} /></View>;
  const ready = state.resume?.status === 'confirmed' && state.resume.reviewStatus === 'ai_verified';

  const start = (focus: TrainingFocus | null = null) => {
    track('interview_entry_clicked', { mode: focus ? 'focused' : 'formal', resume_ready: ready });
    router.push({ pathname: ready ? '/setup' : '/resume', params: focus ? { mode: 'focused', focus } : { mode: 'formal' } });
  };

  const openReport = () => state.report && state.activeSession ? router.push('/report') : showMessage('暂无面试复盘', '完成一次模拟面试后，本次报告和复盘会显示在这里。');

  return <View style={styles.page}><Screen>
    <View style={styles.brand}><Text style={styles.brandText}>AI 面试官</Text><Text style={styles.brandBadge}>P0</Text></View>
    <Card tone={ready ? 'success' : 'warning'}>
      <View style={styles.resumeRow}><Text style={styles.statusIcon}>{ready ? '✅' : '📄'}</Text><View style={styles.flex}>
        <Text style={[styles.resumeTitle, { color: ready ? colors.success : colors.warningText }]}>{ready ? '简历已确认' : '尚未准备有效简历'}</Text>
        <Text numberOfLines={1} style={styles.resumeMeta}>{state.resume?.name ?? '上传并确认 PDF 后，AI 才会基于真实经历提问'}</Text>
      </View><Pressable onPress={() => router.push('/resume')}><Text style={styles.link}>{ready ? '更换' : '上传'}</Text></Pressable></View>
    </Card>

    <View style={styles.quickNav}>
      <Pressable accessibilityRole="button" onPress={() => router.push('/resume')} style={styles.quickItem}><Text style={styles.quickLabel}>你的简历</Text></Pressable>
      <Pressable accessibilityRole="button" onPress={openReport} style={styles.quickItem}><Text style={styles.quickLabel}>面试复盘</Text></Pressable>
      <Pressable accessibilityRole="button" onPress={() => router.push('/interview-hub')} style={[styles.quickItem, styles.quickItemActive]}><Text style={[styles.quickLabel, styles.quickLabelActive]}>模拟面试</Text></Pressable>
    </View>

    <View style={styles.formalCard}>
      <View style={styles.formalTop}><View style={styles.recommend}><Text style={styles.recommendText}>推荐</Text></View><Text style={styles.formalIcon}>🎯</Text></View>
      <Text style={styles.formalTitle}>正式模拟面试</Text><Text style={styles.formalBody}>完整还原面试流程，问题基于已确认简历和目标岗位</Text>
      <View style={styles.tags}>{['自我介绍', '简历深挖', '行为面试', '专业题', 'AI 追问'].map((tag) => <Text key={tag} style={styles.tag}>{tag}</Text>)}</View>
      <Button label="开始正式模拟 →" onPress={() => start()} />
    </View>

    <Text style={styles.sectionTitle}>单项专项训练</Text>
    <View style={styles.grid}>{practices.map((item) => <Pressable accessibilityRole="button" key={item.focus} onPress={() => start(item.focus)} style={[styles.practice, { backgroundColor: item.tint }]}>
      <Text style={styles.practiceIcon}>{item.icon}</Text><Text style={[styles.practiceTitle, { color: item.color }]}>{item.title}</Text><Text style={styles.practiceText}>{item.text}</Text>
    </Pressable>)}</View>

    <Card><Text style={styles.tipTitle}>📌 面试小贴士</Text>{['先上传并确认简历，AI 追问才能围绕真实经历', '首次点击录音时才申请麦克风权限，也可全程文字回答', '回答尽量说明背景、个人行动、结果和数据'].map((tip) => <Text key={tip} style={styles.tip}>· {tip}</Text>)}</Card>
    {state.activeSession?.status === 'active' || state.activeSession?.status === 'paused' ? <Button label="继续上次面试" variant="secondary" onPress={() => router.push('/interview')} /> : null}
  </Screen><BottomNav active="home" onHome={() => undefined} onInterview={() => router.push('/interview-hub')} onReport={openReport} onProfile={() => router.push('/profile')} /></View>;
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.background }, loading: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background }, brand: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: spacing.lg },
  brandText: { ...typography.title, color: colors.primary }, brandBadge: { color: colors.primary, backgroundColor: colors.primarySoft, borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 4, fontWeight: '700' },
  resumeRow: { flexDirection: 'row', alignItems: 'center', gap: 12 }, statusIcon: { fontSize: 24 }, flex: { flex: 1 }, resumeTitle: { fontSize: 16, fontWeight: '800' }, resumeMeta: { color: colors.muted, marginTop: 3, fontSize: 13 }, link: { color: colors.primary, fontWeight: '700' },
  formalCard: { backgroundColor: colors.primary, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.md }, formalTop: { flexDirection: 'row', justifyContent: 'space-between' }, recommend: { backgroundColor: 'rgba(255,255,255,.18)', borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 4 }, recommendText: { color: '#fff', fontWeight: '700' }, formalIcon: { fontSize: 34 },
  formalTitle: { color: '#fff', fontSize: 26, fontWeight: '800' }, formalBody: { color: '#DCE7FF', fontSize: 14, lineHeight: 21 }, tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, tag: { color: '#fff', backgroundColor: 'rgba(255,255,255,.16)', borderRadius: radius.pill, paddingHorizontal: 9, paddingVertical: 4, fontSize: 12 },
  sectionTitle: { ...typography.heading, color: colors.ink, marginTop: spacing.sm }, grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, practice: { width: '48.5%', minHeight: 132, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, padding: spacing.md }, practiceIcon: { fontSize: 28 }, practiceTitle: { fontSize: 17, fontWeight: '800', marginTop: 8 }, practiceText: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 4 },
  tipTitle: { color: colors.ink, fontWeight: '800', marginBottom: 8 }, tip: { color: colors.muted, fontSize: 13, lineHeight: 21 },
  quickNav: { flexDirection: 'row', gap: 10 }, quickItem: { flex: 1, minHeight: 54, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.primary, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 6 }, quickItemActive: { backgroundColor: colors.primary }, quickLabel: { color: colors.primary, fontSize: 15, fontWeight: '800' }, quickLabelActive: { color: '#FFFFFF' },
});
