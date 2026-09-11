import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';
import 'react-native-url-polyfill/auto';

const url = process.env.EXPO_PUBLIC_SUPABASE_URL?.trim();
const publishableKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim();

export const isCloudAuthConfigured = Boolean(url && publishableKey);
const isBrowser = typeof window !== 'undefined';

export const supabase = isCloudAuthConfigured
  ? createClient(url!, publishableKey!, {
      auth: {
        ...(isBrowser ? { storage: AsyncStorage } : {}),
        autoRefreshToken: isBrowser,
        persistSession: isBrowser,
        detectSessionInUrl: false,
      },
    })
  : null;

export async function getAccessToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data, error } = await supabase.auth.getSession();
  if (error) throw error;
  return data.session?.access_token ?? null;
}
