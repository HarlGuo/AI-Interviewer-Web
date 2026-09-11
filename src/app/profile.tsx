import { Href, router } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import { BottomNav, Button, Card, Screen } from '@/components/ui';
import { useApp } from '@/state/app-context';
import { useAuth } from '@/state/auth-context';
import { showMessage } from '@/services/dialogs';
import { colors, spacing, typography } from '@/theme/tokens';

export default function ProfileScreen() {
  const { state } = useApp();
  const { cloudEnabled, user, signOut } = useAuth();
  const openReport = () => state.report && state.activeSession ? router.push('/report') : showMessage('暂无面试报告', '完成一次模拟面试后，本次报告会显示在这里。');

  return <View style={styles.page}>
    <Screen>
      <Text style={styles.title}>我的</Text>
      <Card><Text style={styles.label}>登录账号</Text><Text style={styles.value}>{cloudEnabled ? user?.email ?? '邮箱已验证' : '本地开发模式（未连接云端）'}</Text></Card>
      <Card><Text style={styles.label}>当前简历</Text><Text style={styles.value}>{state.resume?.status === 'confirmed' ? state.resume.name : '尚未确认简历'}</Text></Card>
      <Card><Text style={styles.label}>当前版本</Text><Text style={styles.value}>{cloudEnabled ? '云端账号开发版' : 'P0 本地测试版'}</Text></Card>
      <Card tone="blue"><Text style={styles.note}>简历、回答和报告的云端同步将在 Supabase 项目创建并执行数据库迁移后启用。当前设备缓存已经按账号隔离。</Text></Card>
      {cloudEnabled ? <Button label="退出登录" variant="secondary" onPress={async () => { await signOut(); router.replace('/login' as Href); }} /> : null}
    </Screen>
    <BottomNav active="profile" onHome={() => router.replace('/')} onInterview={() => router.push('/interview-hub')} onReport={openReport} onProfile={() => undefined} />
  </View>;
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.background }, title: { ...typography.title, color: colors.ink, marginTop: spacing.xl }, label: { color: colors.muted, fontSize: 13 }, value: { color: colors.ink, fontSize: 16, fontWeight: '700', marginTop: 6 }, note: { color: colors.primary, lineHeight: 21 },
});
