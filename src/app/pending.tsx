import { StyleSheet, Text, View } from 'react-native';

import { Button, Card, Screen } from '@/components/ui';
import { useAuth } from '@/state/auth-context';
import { colors, spacing, typography } from '@/theme/tokens';

export default function PendingScreen() {
  const { accountStatus, refreshAccountStatus, signOut, user } = useAuth();
  const copy = accountStatus === 'rejected' ? ['申请未通过', '如有疑问，请联系邀请你参与测试的管理员。']
    : accountStatus === 'suspended' ? ['账号已暂停', '该账号当前无法使用面试服务。']
    : ['注册申请已提交', '管理员通过审核后，你即可使用全部内测功能。'];
  return <Screen>
    <View style={styles.hero}><Text style={styles.title}>{copy[0]}</Text><Text style={styles.subtitle}>{copy[1]}</Text></View>
    <Card><Text style={styles.label}>申请邮箱</Text><Text style={styles.email}>{user?.email ?? '未知邮箱'}</Text><Text style={styles.tip}>审核状态不会消耗面试次数。通过后点击“刷新审核状态”。</Text>
      <Button label="刷新审核状态" onPress={refreshAccountStatus} /><Button label="退出登录" onPress={signOut} variant="ghost" />
    </Card>
  </Screen>;
}

const styles = StyleSheet.create({ hero: { marginTop: spacing.xl, marginBottom: spacing.lg }, title: { ...typography.title, color: colors.ink }, subtitle: { color: colors.muted, marginTop: 8, lineHeight: 22 }, label: { color: colors.muted }, email: { color: colors.ink, fontWeight: '700', marginTop: 6 }, tip: { color: colors.muted, lineHeight: 21, marginVertical: spacing.lg } });
