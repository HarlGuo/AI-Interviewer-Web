import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { Button, Card, Screen } from '@/components/ui';
import { flushTelemetry, getAcquisitionProperties, track } from '@/services/telemetry';
import { useAuth } from '@/state/auth-context';
import { colors, radius, spacing, typography } from '@/theme/tokens';

export default function LoginScreen() {
  const { register, signIn } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [analyticsAgreed, setAnalyticsAgreed] = useState(false);
  const submit = async () => {
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError('请输入有效的邮箱地址。');
    if (password.length < 8) return setError('密码至少需要 8 个字符。');
    if (!analyticsAgreed) return setError('请先同意内测数据说明。');
    setBusy(true); setError(''); setMessage('');
    const acquisition = getAcquisitionProperties();
    track(mode === 'register' ? 'registration_submitted' : 'landing_viewed', acquisition);
    try {
      await (mode === 'register' ? register(email, password) : signIn(email, password));
      track(mode === 'register' ? 'registration_created' : 'sign_in_succeeded', acquisition);
      await flushTelemetry();
      if (mode === 'register') setMessage('注册成功，请等待管理员确认。');
    }
    catch (cause) { track(mode === 'register' ? 'registration_failed' : 'sign_in_failed', { ...acquisition, error_code: 'auth_failed' }); setError(cause instanceof Error ? cause.message : '操作失败，请稍后重试。'); }
    finally { setBusy(false); }
  };
  return <Screen>
    <View style={styles.hero}><Text style={styles.title}>{mode === 'register' ? '申请内测账号' : '登录 AI 面试官'}</Text><Text style={styles.subtitle}>{mode === 'register' ? '提交后需由管理员人工审核，通过后才能开始面试。' : '使用已注册的邮箱和密码登录。'}</Text></View>
    <Card>
      <Text style={styles.label}>邮箱</Text>
      <TextInput accessibilityLabel="邮箱" autoCapitalize="none" autoComplete="email" keyboardType="email-address" onChangeText={setEmail} placeholder="name@example.com" style={styles.input} value={email} />
      <Text style={styles.label}>密码</Text>
      <TextInput accessibilityLabel="密码" autoCapitalize="none" autoComplete={mode === 'register' ? 'new-password' : 'current-password'} onChangeText={setPassword} placeholder="至少 8 个字符" secureTextEntry style={styles.input} value={password} />
      <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: analyticsAgreed }} onPress={() => setAnalyticsAgreed((value) => !value)} style={styles.agreement}><View style={[styles.checkbox, analyticsAgreed && styles.checkboxOn]}><Text style={styles.check}>{analyticsAgreed ? '✓' : ''}</Text></View><Text style={styles.agreementText}>我同意内测期间记录匿名产品事件、错误类型和模型 Token 用量，用于改进产品；不记录简历、问题、回答或录音正文。</Text></Pressable>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {message ? <Text style={styles.success}>{message}</Text> : null}
      {busy ? <ActivityIndicator color={colors.primary} /> : null}
      <Button disabled={busy} label={mode === 'register' ? '提交注册申请' : '登录'} onPress={submit} />
      <Button disabled={busy} label={mode === 'register' ? '已有账号，返回登录' : '没有账号，申请内测'} onPress={() => { setMode(mode === 'register' ? 'login' : 'register'); setError(''); setMessage(''); }} variant="ghost" />
    </Card>
    <Text style={styles.notice}>测试阶段暂不验证邮箱。请使用你能长期访问的真实邮箱；正式上线前将启用邮箱验证、找回密码、用户协议和隐私政策。</Text>
  </Screen>;
}

const styles = StyleSheet.create({
  hero: { marginTop: spacing.xl, marginBottom: spacing.lg }, title: { ...typography.title, color: colors.ink }, subtitle: { color: colors.muted, lineHeight: 21, marginTop: 8 },
  label: { color: colors.ink, fontWeight: '700', marginBottom: 7 }, input: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, paddingHorizontal: 14, minHeight: 50, color: colors.ink, backgroundColor: colors.surface, marginBottom: spacing.md },
  error: { color: colors.danger, lineHeight: 20, marginBottom: spacing.sm }, success: { color: colors.success, lineHeight: 20, marginBottom: spacing.sm, fontWeight: '700' }, notice: { color: colors.muted, fontSize: 12, lineHeight: 18, textAlign: 'center' },
  agreement: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, marginBottom: spacing.md }, checkbox: { width: 22, height: 22, borderRadius: 5, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }, checkboxOn: { backgroundColor: colors.primary, borderColor: colors.primary }, check: { color: '#fff', fontWeight: '900' }, agreementText: { flex: 1, color: colors.muted, fontSize: 12, lineHeight: 18 },
});
