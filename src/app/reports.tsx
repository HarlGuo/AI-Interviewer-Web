import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { BottomNav, Card, Screen } from '@/components/ui';
import { useApp } from '@/state/app-context';
import { colors, radius, spacing, typography } from '@/theme/tokens';

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(date);
}

export default function ReportsScreen() {
  const { state, selectReport } = useApp();
  const openReport = async (reportId: string) => {
    await selectReport(reportId);
    router.push('/report');
  };

  return <View style={styles.page}><Screen>
    <Text style={styles.title}>面试复盘</Text>
    <Text style={styles.subtitle}>回看已完成面试的评分依据、回答证据和改进建议。</Text>
    {state.reportHistory.length ? state.reportHistory.map((item) => <Pressable accessibilityRole="button" key={item.id} onPress={() => void openReport(item.id)} style={styles.record}>
      <View style={styles.recordTop}><View style={styles.flex}><Text style={styles.role}>{item.target.title}</Text><Text style={styles.meta}>{item.mode === 'formal' ? '正式模拟' : '单项训练'} · {item.status === 'ended-early' ? '提前结束' : '已完成'}</Text></View><Text style={styles.score}>{item.report.overall_score}</Text></View>
      <View style={styles.recordBottom}><Text style={styles.date}>{formatDate(item.completedAt)}</Text><Text style={styles.link}>查看报告 →</Text></View>
    </Pressable>) : <Card><Text style={styles.emptyTitle}>还没有面试报告</Text><Text style={styles.emptyText}>完成一次模拟面试并生成报告后，可在这里随时查看和复盘。</Text></Card>}
  </Screen><BottomNav active="report" onHome={() => router.replace('/')} onInterview={() => router.push('/interview-hub')} onReport={() => undefined} onProfile={() => router.push('/profile')} /></View>;
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.background }, title: { ...typography.title, color: colors.ink, marginTop: spacing.xl }, subtitle: { color: colors.muted, lineHeight: 22 },
  record: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, padding: spacing.md, gap: spacing.md },
  recordTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.md }, flex: { flex: 1 }, role: { color: colors.ink, fontSize: 18, fontWeight: '800' }, meta: { color: colors.muted, fontSize: 13, marginTop: 5 }, score: { color: colors.primary, fontSize: 30, fontWeight: '900' },
  recordBottom: { flexDirection: 'row', justifyContent: 'space-between', borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.sm }, date: { color: colors.muted, fontSize: 12 }, link: { color: colors.primary, fontWeight: '700' },
  emptyTitle: { color: colors.ink, fontSize: 17, fontWeight: '800' }, emptyText: { color: colors.muted, lineHeight: 21, marginTop: spacing.sm },
});
