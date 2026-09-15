import { Href, Stack, router, useSegments } from 'expo-router';
import { useEffect } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';

import { AppProvider } from '@/state/app-context';
import { AuthProvider, useAuth } from '@/state/auth-context';
import { flushTelemetry, track } from '@/services/telemetry';
import { colors } from '@/theme/tokens';

export default function RootLayout() {
  return (
    <AuthProvider><AppProvider>
      <StatusBar style="dark" />
      <ProtectedStack />
    </AppProvider></AuthProvider>
  );
}

function ProtectedStack() {
  const { ready, cloudEnabled, user, accountStatus, statusLoading } = useAuth();
  const segments = useSegments();
  useEffect(() => {
    if (!ready || !cloudEnabled || !user) return;
    track('authenticated_session_started');
    void flushTelemetry();
  }, [cloudEnabled, ready, user?.id]);
  useEffect(() => {
    if (!ready || !cloudEnabled) return;
    const onLogin = (segments[0] as string | undefined) === 'login';
    const onPending = (segments[0] as string | undefined) === 'pending';
    if (!user && !onLogin) router.replace('/login' as Href);
    if (user && accountStatus !== 'approved' && !onPending) router.replace('/pending' as Href);
    if (user && accountStatus === 'approved' && (onLogin || onPending)) router.replace('/');
  }, [accountStatus, cloudEnabled, ready, segments, user]);
  if (!ready || (user && statusLoading)) return <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background }}><ActivityIndicator color={colors.primary} /></View>;
  return <Stack screenOptions={{ headerBackTitle: '返回', headerShadowVisible: false, headerStyle: { backgroundColor: colors.surface }, headerTitleStyle: { color: colors.ink, fontWeight: '700' }, contentStyle: { backgroundColor: colors.background } }}>
        <Stack.Screen name="login" options={{ headerShown: false }} />
        <Stack.Screen name="pending" options={{ headerShown: false }} />
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="resume" options={{ title: '上传与确认简历' }} />
        <Stack.Screen name="interview-hub" options={{ headerShown: false }} />
        <Stack.Screen name="setup" options={{ title: '面试设置' }} />
        <Stack.Screen name="interview" options={{ title: '模拟面试', headerBackVisible: false }} />
        <Stack.Screen name="report" options={{ title: '面试报告', headerBackVisible: false }} />
        <Stack.Screen name="profile" options={{ headerShown: false }} />
      </Stack>;
}
