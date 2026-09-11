import { Alert, Platform } from 'react-native';

export function showMessage(title: string, message: string) {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    window.alert(`${title}\n\n${message}`);
    return;
  }
  Alert.alert(title, message);
}

export function confirmAction(options: { title: string; message: string; confirmText?: string; cancelText?: string; destructive?: boolean; onConfirm: () => void | Promise<void> }) {
  const { title, message, confirmText = '确认', cancelText = '取消', destructive = false, onConfirm } = options;
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    if (window.confirm(`${title}\n\n${message}`)) void onConfirm();
    return;
  }
  Alert.alert(title, message, [
    { text: cancelText, style: 'cancel' },
    { text: confirmText, style: destructive ? 'destructive' : 'default', onPress: () => { void onConfirm(); } },
  ]);
}
