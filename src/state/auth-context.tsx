import { Session, User } from '@supabase/supabase-js';
import { createContext, PropsWithChildren, useContext, useEffect, useMemo, useState } from 'react';

import { isCloudAuthConfigured, supabase } from '@/services/supabase';

type AuthContextValue = {
  ready: boolean;
  cloudEnabled: boolean;
  session: Session | null;
  user: User | null;
  accountStatus: 'pending' | 'approved' | 'rejected' | 'suspended' | 'deletion_pending' | 'disabled' | null;
  statusLoading: boolean;
  localUserId: string;
  register: (email: string, password: string) => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  refreshAccountStatus: () => Promise<void>;
  signOut: () => Promise<void>;
};

const LOCAL_DEVELOPMENT_USER_ID = 'local-development-user';
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [ready, setReady] = useState(!isCloudAuthConfigured);
  const [session, setSession] = useState<Session | null>(null);
  const [accountStatus, setAccountStatus] = useState<AuthContextValue['accountStatus']>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const loadAccountStatus = async (nextSession: Session | null) => {
    if (!supabase || !nextSession) { setAccountStatus(null); return; }
    setStatusLoading(true);
    const { data, error } = await supabase.from('profiles').select('account_status').eq('user_id', nextSession.user.id).single();
    setStatusLoading(false);
    if (error) throw error;
    setAccountStatus(data.account_status as AuthContextValue['accountStatus']);
  };

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => {
      setSession(data.session); void loadAccountStatus(data.session).catch(() => setAccountStatus(null));
      setReady(true);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession); void loadAccountStatus(nextSession).catch(() => setAccountStatus(null));
    });
    return () => data.subscription.unsubscribe();
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    ready,
    cloudEnabled: isCloudAuthConfigured,
    session,
    user: session?.user ?? null,
    accountStatus,
    statusLoading,
    localUserId: session?.user.id ?? LOCAL_DEVELOPMENT_USER_ID,
    register: async (email, password) => {
      if (!supabase) throw new Error('云端账号服务尚未配置');
      const { data, error } = await supabase.auth.signUp({ email: email.trim(), password });
      if (error) throw error;
      if (!data.user) throw new Error('注册申请未能创建，请稍后重试。');
    },
    signIn: async (email, password) => {
      if (!supabase) throw new Error('云端账号服务尚未配置');
      const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
      if (error) throw error;
    },
    refreshAccountStatus: async () => loadAccountStatus(session),
    signOut: async () => {
      if (!supabase) return;
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
    },
  }), [accountStatus, ready, session, statusLoading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
}
