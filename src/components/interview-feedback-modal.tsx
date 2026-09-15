import { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { FeedbackSubmission } from '@/domain/models';
import { colors, radius, spacing, typography } from '@/theme/tokens';

const tagOptions: FeedbackSubmission['tags'] = ['问题贴合简历', '追问有深度', '等待太久', '语音体验不顺', '问题重复'];
const paymentOptions: { value: FeedbackSubmission['payment_willingness']; label: string }[] = [
  { value: 'willing', label: '愿意' },
  { value: 'depends_on_price', label: '取决于价格' },
  { value: 'unwilling', label: '不愿意' },
  { value: 'prefer_not_to_say', label: '暂不回答' },
];

export function InterviewFeedbackModal({ visible, completionType, submitting, error, onSubmit, onSkip }: {
  visible: boolean;
  completionType: 'completed' | 'ended_early';
  submitting: boolean;
  error: string;
  onSubmit: (feedback: FeedbackSubmission) => Promise<void>;
  onSkip: () => void;
}) {
  const [score, setScore] = useState<number | null>(null);
  const [payment, setPayment] = useState<FeedbackSubmission['payment_willingness'] | null>(null);
  const [tags, setTags] = useState<FeedbackSubmission['tags']>([]);
  const [comment, setComment] = useState('');
  const toggleTag = (tag: FeedbackSubmission['tags'][number]) => setTags((current) => current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag]);
  const ready = score !== null && payment !== null;

  return <Modal visible={visible} transparent animationType="fade" onRequestClose={onSkip}>
    <View style={styles.backdrop}><View style={styles.panel}>
      <Text style={styles.title}>这次面试体验怎么样？</Text>
      <Text style={styles.helper}>反馈用于改进问题质量和使用体验，不会影响面试评分。</Text>
      <Text style={styles.label}>满意度（必选）</Text>
      <View style={styles.row}>{[1, 2, 3, 4, 5].map((value) => <Pressable key={value} onPress={() => setScore(value)} style={[styles.choice, score === value && styles.selected]}><Text style={[styles.choiceText, score === value && styles.selectedText]}>{value}</Text></Pressable>)}</View>
      <Text style={styles.label}>未来是否愿意付费参加 AI 面试训练？（必选）</Text>
      <View style={styles.wrap}>{paymentOptions.map((item) => <Pressable key={item.value} onPress={() => setPayment(item.value)} style={[styles.pill, payment === item.value && styles.selected]}><Text style={[styles.pillText, payment === item.value && styles.selectedText]}>{item.label}</Text></Pressable>)}</View>
      <Text style={styles.label}>可选标签</Text>
      <View style={styles.wrap}>{tagOptions.map((tag) => <Pressable key={tag} onPress={() => toggleTag(tag)} style={[styles.pill, tags.includes(tag) && styles.selected]}><Text style={[styles.pillText, tags.includes(tag) && styles.selectedText]}>{tag}</Text></Pressable>)}</View>
      <TextInput value={comment} onChangeText={setComment} maxLength={500} multiline placeholder="其他建议（选填）" placeholderTextColor={colors.placeholder} style={styles.input} />
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <View style={styles.actions}>
        <Pressable disabled={submitting} onPress={onSkip} style={styles.skip}><Text style={styles.skipText}>暂不反馈</Text></Pressable>
        <Pressable disabled={!ready || submitting} onPress={() => ready && onSubmit({ satisfaction_score: score, payment_willingness: payment, tags, comment: comment.trim(), completion_type: completionType })} style={[styles.submit, (!ready || submitting) && styles.disabled]}><Text style={styles.submitText}>{submitting ? '提交中…' : '提交反馈'}</Text></Pressable>
      </View>
    </View></View>
  </Modal>;
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(16,24,40,.55)', alignItems: 'center', justifyContent: 'center', padding: spacing.lg },
  panel: { width: '100%', maxWidth: 560, backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.sm },
  title: { ...typography.heading, color: colors.ink }, helper: { color: colors.muted, lineHeight: 20 }, label: { color: colors.ink, fontWeight: '800', marginTop: spacing.sm },
  row: { flexDirection: 'row', gap: 8 }, wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  choice: { flex: 1, minHeight: 42, borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, alignItems: 'center', justifyContent: 'center' },
  choiceText: { color: colors.muted, fontWeight: '800' }, pill: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, paddingHorizontal: 12, paddingVertical: 8 }, pillText: { color: colors.muted }, selected: { backgroundColor: colors.primary, borderColor: colors.primary }, selectedText: { color: '#fff' },
  input: { minHeight: 76, borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, padding: 12, color: colors.ink, textAlignVertical: 'top', marginTop: spacing.sm },
  error: { color: colors.danger, fontSize: 12 }, actions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10, marginTop: spacing.sm }, skip: { padding: 12 }, skipText: { color: colors.muted, fontWeight: '700' }, submit: { backgroundColor: colors.primary, borderRadius: radius.sm, paddingHorizontal: 18, paddingVertical: 12 }, disabled: { opacity: .45 }, submitText: { color: '#fff', fontWeight: '800' },
});
