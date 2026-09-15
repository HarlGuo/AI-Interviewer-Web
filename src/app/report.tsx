import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { BottomNav, Button, Card, Screen } from '@/components/ui';
import { interviewGateway } from '@/services/gateways';
import { track } from '@/services/telemetry';
import { useApp } from '@/state/app-context';
import { colors, radius, spacing, typography } from '@/theme/tokens';

export default function ReportScreen() {
  const { state, saveReport, clearSession } = useApp(); const [loading, setLoading] = useState(false); const [error, setError] = useState(''); const [expanded, setExpanded] = useState<number | null>(null); const requested = useRef(false);
  const session = state.activeSession; const report = state.report;

  const generate = async () => {
    if (!session?.answers.length || !session.interviewId || loading) return; setLoading(true); setError(''); const startedAt = Date.now(); track('report_generation_started', {}, session.interviewId);
    try { await saveReport(await interviewGateway.report(session)); track('report_generation_succeeded', { latency_ms: Date.now() - startedAt }, session.interviewId); }
    catch (cause) { track('report_generation_failed', { error_code: 'request_failed', latency_ms: Date.now() - startedAt }, session.interviewId); setError(cause instanceof Error ? cause.message : '请检查网络、后端和 DeepSeek 配置。'); }
    finally { setLoading(false); }
  };
  useEffect(() => { if (session?.answers.length && !report && !requested.current) { requested.current = true; void generate(); } }, [session, report]);
  useEffect(() => { if (report) track('report_viewed', { completed: session?.status === 'completed' }, session?.interviewId); }, [report]);
  const finish = async () => { await clearSession(); router.replace('/'); };
  if (!session) return <Screen><Text style={styles.title}>没有可用的面试记录</Text><Button label="返回首页" onPress={() => router.replace('/')} /></Screen>;

  return <View style={styles.page}><Screen>
    <Text style={styles.title}>{report ? '本次面试报告' : '正在生成面试报告'}</Text>
    {report ? <><Button label={loading ? '正在重新生成…' : '使用已保存回答重新生成报告'} variant="secondary" disabled={loading} onPress={() => void generate()} />{error ? <Text style={styles.regenerateError}>{error}</Text> : null}</> : null}
    {!report ? <Card tone={error ? 'warning' : 'blue'}>{loading ? <><ActivityIndicator color={colors.primary} size="large" /><Text style={styles.loadingTitle}>正在按统一量表分析回答</Text><Text style={styles.body}>正在核对六个维度和每道回答的原文证据，通常需要 1–3 分钟。请保持页面打开，不要重复生成。</Text></> : <><Text style={styles.errorTitle}>报告生成失败</Text><Text style={styles.body}>{error}</Text><Button label="重新生成" onPress={() => { requested.current = true; void generate(); }} /></>}</Card> : <>
      <View style={styles.scoreCard}><View><Text style={styles.scoreLabel}>{session.target.title} · {session.mode === 'formal' ? '正式模拟' : '单项训练'}</Text><Text style={styles.completion}>{report.completion}</Text></View><View style={styles.scoreCircle}><Text style={styles.score}>{report.overall_score}</Text><Text style={styles.scoreUnit}>综合分</Text></View></View>
      <Card><Text style={styles.cardTitle}>总体评价</Text><Text style={styles.body}>{report.summary}</Text><View style={styles.notice}><Text style={styles.noticeText}>{report.evidence_notice}</Text></View></Card>
      <Text style={styles.sectionTitle}>维度评分</Text>{report.dimensions.map((item) => <Card key={item.name}><View style={styles.dimensionHeader}><View><Text style={styles.cardTitle}>{item.name}</Text><Text style={styles.level}>{item.level ? `行为等级 ${item.level}/5` : '证据不足'}</Text></View><Text style={[styles.dimensionScore, item.score === null && styles.noScore]}>{item.score ?? '—'}</Text></View>{item.score !== null ? <View style={styles.bar}><View style={[styles.barFill, { width: `${item.score}%` }]} /></View> : null}<Text style={styles.body}>{item.basis}</Text>{item.evidence.length ? <><Text style={styles.subhead}>回答证据</Text>{item.evidence.map((value, index) => <Text key={`${value}-${index}`} style={styles.quote}>“{value}”</Text>)}</> : null}<Text style={styles.subhead}>下一步</Text><Text style={styles.body}>{item.suggestion}</Text></Card>)}
      <Text style={styles.sectionTitle}>单题分析</Text>{report.question_reviews.map((item, index) => <View key={`${item.question_id}-${index}`} style={styles.review}><Pressable onPress={() => { const next = expanded === index ? null : index; setExpanded(next); if (next !== null) track('report_advice_viewed', { question_index: index }, session.interviewId); }} style={styles.reviewHeader}><Text style={styles.reviewTitle}>第 {index + 1} 题复盘</Text><Text style={styles.chevron}>{expanded === index ? '▾' : '▸'}</Text></Pressable>{expanded === index ? <View style={styles.reviewBody}>{item.strengths.map((value, i) => <Text key={`s-${i}`} style={styles.good}>✓ {value}</Text>)}{item.issues.map((value, i) => <Text key={`i-${i}`} style={styles.issue}>• {value}</Text>)}{item.evidence.map((value, i) => <Text key={`e-${i}`} style={styles.quote}>“{value}”</Text>)}<View style={styles.advice}><Text style={styles.adviceTitle}>改进建议</Text><Text style={styles.adviceText}>{item.suggestion}</Text></View></View> : null}</View>)}
    </>}
    <Button label="返回首页" variant={report ? 'primary' : 'ghost'} onPress={finish} />
    <Text style={styles.disclaimer}>评分采用公开的结构化面试行为锚定方法，仅用于练习反馈，不代表录用概率。</Text>
  </Screen><BottomNav active="report" onHome={() => router.replace('/')} onInterview={() => router.push('/interview-hub')} onReport={() => undefined} onProfile={() => router.push('/profile')} /></View>;
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.background },
  title: { ...typography.title, color: colors.ink, marginTop: spacing.md }, loadingTitle: { ...typography.heading, color: colors.primary, textAlign: 'center', marginTop: spacing.md }, errorTitle: { ...typography.heading, color: colors.warningText }, body: { ...typography.body, color: colors.muted, marginTop: 7 }, scoreCard: { backgroundColor: colors.primary, borderRadius: radius.lg, padding: spacing.lg, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, scoreLabel: { color: '#DCE7FF', fontSize: 14 }, completion: { color: '#fff', fontWeight: '800', marginTop: 8, fontSize: 18 }, scoreCircle: { width: 90, height: 90, borderRadius: 45, borderWidth: 6, borderColor: '#80A9FF', alignItems: 'center', justifyContent: 'center' }, score: { color: '#fff', fontSize: 34, fontWeight: '900' }, scoreUnit: { color: '#DCE7FF', fontSize: 11 },
  cardTitle: { color: colors.ink, fontWeight: '800', fontSize: 17 }, notice: { backgroundColor: colors.warningSoft, borderRadius: radius.sm, padding: 10, marginTop: 12 }, noticeText: { color: colors.warningText, fontSize: 12, lineHeight: 18 }, sectionTitle: { ...typography.heading, color: colors.ink, marginTop: spacing.sm }, dimensionHeader: { flexDirection: 'row', justifyContent: 'space-between' }, level: { color: colors.muted, fontSize: 12, marginTop: 3 }, dimensionScore: { color: colors.primary, fontWeight: '900', fontSize: 28 }, noScore: { color: colors.muted }, bar: { height: 6, backgroundColor: colors.surfaceMuted, borderRadius: 3, overflow: 'hidden', marginVertical: 12 }, barFill: { height: '100%', backgroundColor: colors.primary }, subhead: { color: colors.ink, fontWeight: '800', fontSize: 13, marginTop: 12 }, quote: { color: colors.ink, fontSize: 13, lineHeight: 20, marginTop: 4 },
  review: { borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, borderRadius: radius.lg, overflow: 'hidden' }, reviewHeader: { flexDirection: 'row', justifyContent: 'space-between', padding: spacing.md }, reviewTitle: { color: colors.ink, fontWeight: '800' }, chevron: { color: colors.muted }, reviewBody: { padding: spacing.md, borderTopWidth: 1, borderTopColor: colors.border, gap: 7 }, good: { color: colors.success, lineHeight: 20 }, issue: { color: colors.danger, lineHeight: 20 }, advice: { backgroundColor: colors.primarySoft, borderRadius: radius.sm, padding: 12, marginTop: 6 }, adviceTitle: { color: colors.primary, fontWeight: '800' }, adviceText: { color: colors.primary, lineHeight: 20, marginTop: 4 }, regenerateError: { color: colors.danger, fontSize: 12, lineHeight: 18, textAlign: 'center' }, disclaimer: { color: colors.muted, fontSize: 11, lineHeight: 17, textAlign: 'center' },
});
