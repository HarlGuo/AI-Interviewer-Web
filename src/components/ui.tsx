import { PropsWithChildren } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { colors, radius, spacing } from '@/theme/tokens';

export function Screen({ children, keyboard = false }: PropsWithChildren<{ keyboard?: boolean }>) {
  const content = <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.content}>{children}</ScrollView>;
  return (
    <SafeAreaView style={styles.safe} edges={['bottom', 'left', 'right']}>
      {keyboard ? <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>{content}</KeyboardAvoidingView> : content}
    </SafeAreaView>
  );
}

export function Card({ children, tone = 'default' }: PropsWithChildren<{ tone?: 'default' | 'blue' | 'success' | 'warning' }>) { return <View style={[styles.card, styles[`card_${tone}`]]}>{children}</View>; }

export function Button({ label, onPress, variant = 'primary', compact = false, disabled = false }: { label: string; onPress: () => void; variant?: 'primary' | 'secondary' | 'ghost'; compact?: boolean; disabled?: boolean }) {
  return (
    <Pressable accessibilityRole="button" disabled={disabled} onPress={onPress} style={({ pressed }) => [styles.button, compact && styles.buttonCompact, styles[`button_${variant}`], pressed && !disabled && styles.pressed, disabled && styles.disabled]}>
      <Text style={[styles.buttonText, styles[`buttonText_${variant}`]]}>{label}</Text>
    </Pressable>
  );
}

export function BottomNav({ active = 'home', onHome, onInterview, onReport, onProfile }: { active?: 'home' | 'interview' | 'report' | 'profile'; onHome: () => void; onInterview: () => void; onReport: () => void; onProfile: () => void }) {
  const items = [{ id: 'home' as const, icon: '⌂', label: '首页', onPress: onHome }, { id: 'interview' as const, icon: '◉', label: '面试', onPress: onInterview }, { id: 'report' as const, icon: '▤', label: '面试报告', onPress: onReport }, { id: 'profile' as const, icon: '♙', label: '我的', onPress: onProfile }];
  return <View style={styles.bottomNav}>{items.map((item) => <Pressable accessibilityRole="button" key={item.id} onPress={item.onPress} style={styles.bottomItem}><Text style={[styles.bottomIcon, active === item.id && styles.bottomActive]}>{item.icon}</Text><Text style={[styles.bottomLabel, active === item.id && styles.bottomActive]}>{item.label}</Text></Pressable>)}</View>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background }, flex: { flex: 1 },
  content: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xxl, gap: spacing.md, width: '100%', maxWidth: 640, alignSelf: 'center' },
  card: { backgroundColor: colors.surface, padding: spacing.md, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border },
  card_default: {}, card_blue: { backgroundColor: colors.primarySoft, borderColor: '#BED3FF' }, card_success: { backgroundColor: colors.successSoft, borderColor: '#B7F5C8' }, card_warning: { backgroundColor: colors.warningSoft, borderColor: '#FFD666' },
  button: { minHeight: 52, paddingHorizontal: spacing.lg, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' },
  buttonCompact: { minHeight: 38, paddingHorizontal: 14, alignSelf: 'flex-start' },
  button_primary: { backgroundColor: colors.primary }, button_secondary: { backgroundColor: colors.primarySoft, borderWidth: 1, borderColor: '#BED3FF' }, button_ghost: { backgroundColor: 'transparent' },
  buttonText: { fontSize: 16, fontWeight: '700' }, buttonText_primary: { color: '#FFFFFF' }, buttonText_secondary: { color: colors.primary }, buttonText_ghost: { color: colors.muted },
  pressed: { opacity: 0.78 }, disabled: { opacity: 0.42 },
  bottomNav: { flexDirection: 'row', backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 7, paddingBottom: 5 }, bottomItem: { flex: 1, alignItems: 'center', gap: 1 }, bottomIcon: { color: colors.muted, fontSize: 22, fontWeight: '700' }, bottomLabel: { color: colors.muted, fontSize: 10, fontWeight: '600' }, bottomActive: { color: colors.primary },
});
