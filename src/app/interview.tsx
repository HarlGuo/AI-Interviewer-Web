import { ExpoSpeechRecognitionModule, useSpeechRecognitionEvent } from 'expo-speech-recognition';
import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { Button, Card, Screen } from '@/components/ui';
import { ApiNotConfiguredError, interviewGateway } from '@/services/gateways';
import { confirmAction, showMessage } from '@/services/dialogs';
import { track } from '@/services/telemetry';
import { useApp } from '@/state/app-context';
import { colors, radius, spacing, typography } from '@/theme/tokens';

export default function InterviewScreen() {
  const { state, activateSession, updateAnswerDraft, applyInterviewTurn, setSessionStatus, clearSession } = useApp();
  const session = state.activeSession;
  const [answer, setAnswer] = useState(session?.answerDraft ?? ''); const [starting, setStarting] = useState(false); const [submitting, setSubmitting] = useState(false); const [decisionNote, setDecisionNote] = useState(''); const [recognizing, setRecognizing] = useState(false); const [speechStatus, setSpeechStatus] = useState(''); const startLock = useRef(false);
  const currentQuestionId = session?.questions[session.currentIndex]?.id ?? null;
  const keepListeningRef = useRef(false); const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null); const autoSubmitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null); const answerBeforeSpeechRef = useRef(''); const finalSpeechRef = useRef(''); const answerRef = useRef(session?.answerDraft ?? ''); const pendingAutoSubmitRef = useRef(false); const submittingRef = useRef(false); const submitLatestRef = useRef<() => Promise<void>>(async () => undefined); const previousQuestionIdRef = useRef(currentQuestionId);

  const joinTranscript = (base: string, speech: string) => [base.trim(), speech.trim()].filter(Boolean).join(base.trim() && speech.trim() ? '\n' : '');
  const setCurrentAnswer = (text: string) => { answerRef.current = text; setAnswer(text); };
  const resetAnswerInput = () => {
    answerBeforeSpeechRef.current = ''; finalSpeechRef.current = ''; answerRef.current = '';
    pendingAutoSubmitRef.current = false; setAnswer(''); setSpeechStatus('');
  };
  const startRecognizer = () => {
    const onDevice = ExpoSpeechRecognitionModule.supportsOnDeviceRecognition();
    ExpoSpeechRecognitionModule.start({
      lang: 'zh-CN', interimResults: true, maxAlternatives: 1, continuous: true,
      requiresOnDeviceRecognition: onDevice, addsPunctuation: true,
      androidIntentOptions: {
        EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS: 10000,
        EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS: 5000,
      },
    });
  };

  useSpeechRecognitionEvent('start', () => { setRecognizing(true); setSpeechStatus('正在聆听，请自然作答；短暂停顿不会结束本题。'); });
  useSpeechRecognitionEvent('end', () => {
    if (keepListeningRef.current) {
      setSpeechStatus('检测到短暂停顿，正在继续聆听…');
      restartTimerRef.current = setTimeout(() => {
        if (!keepListeningRef.current) return;
        try { startRecognizer(); }
        catch { keepListeningRef.current = false; setRecognizing(false); setSpeechStatus('语音识别已停止，已识别文字仍然保留。'); }
      }, 250);
      return;
    }
    setRecognizing(false);
    if (pendingAutoSubmitRef.current) {
      setSpeechStatus('录音回答已结束，正在提交给面试官…');
      autoSubmitTimerRef.current = setTimeout(() => void submitLatestRef.current(), 300);
    } else setSpeechStatus((current) => current || '语音输入已结束，文字仍可编辑。');
  });
  useSpeechRecognitionEvent('result', (event) => {
    if (submittingRef.current) return;
    const transcript = event.results[0]?.transcript?.trim();
    if (!transcript) return;
    if (event.isFinal) finalSpeechRef.current = joinTranscript(finalSpeechRef.current, transcript);
    setCurrentAnswer(joinTranscript(answerBeforeSpeechRef.current, event.isFinal ? finalSpeechRef.current : joinTranscript(finalSpeechRef.current, transcript)));
    setSpeechStatus(event.isFinal ? '已记录这一段，仍在继续聆听…' : '正在生成转写文字…');
  });
  useSpeechRecognitionEvent('error', (event) => {
    if (keepListeningRef.current && (event.error === 'no-speech' || event.error === 'speech-timeout')) {
      setSpeechStatus('暂时没有识别到语音，仍在继续聆听…'); return;
    }
    keepListeningRef.current = false; setRecognizing(false);
    if (event.error === 'aborted') return;
    const messages: Partial<Record<typeof event.error, string>> = {
      'not-allowed': '未获得麦克风或语音识别权限，可在系统设置中开启，或直接输入文字。',
      'no-speech': '没有识别到语音，请靠近麦克风重试，或直接输入文字。',
      'speech-timeout': '等待语音超时，请重新开始语音输入。',
      'language-not-supported': '设备尚未提供中文识别模型，可下载离线模型或直接输入文字。',
      network: '系统语音识别网络连接失败，回答文字仍会保留。',
      'service-not-allowed': '此设备当前无法使用系统语音识别，请直接输入文字。',
    };
    const message = messages[event.error] ?? `语音识别失败：${event.message || event.error}`;
    setSpeechStatus(message); showMessage('转写未完成', message);
  });
  useEffect(() => () => {
    keepListeningRef.current = false;
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    if (autoSubmitTimerRef.current) clearTimeout(autoSubmitTimerRef.current);
    ExpoSpeechRecognitionModule.abort();
  }, []);
  useEffect(() => {
    if (previousQuestionIdRef.current === currentQuestionId) return;
    previousQuestionIdRef.current = currentQuestionId;
    keepListeningRef.current = false;
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    if (autoSubmitTimerRef.current) clearTimeout(autoSubmitTimerRef.current);
    ExpoSpeechRecognitionModule.abort();
    resetAnswerInput();
  }, [currentQuestionId]);
  if (!session) return <Screen><Text style={styles.title}>没有可恢复的面试</Text><Button label="返回首页" onPress={() => router.replace('/')} /></Screen>;

  const startInterview = async () => {
    if (startLock.current) return; startLock.current = true; setStarting(true);
    try {
      if (!state.resume || state.resume.reviewStatus !== 'ai_verified' || state.resume.status !== 'confirmed') throw new Error('请先完成简历解析、AI 复核和用户确认。');
      const result = await interviewGateway.start(session, state.resume); await activateSession(result.interview_id, result.question, result.total_main_questions); track('interview_started', { question_source: result.source, mode: session.mode });
    } catch (error) { showMessage(error instanceof ApiNotConfiguredError ? '后端地址尚未配置' : '面试启动失败', error instanceof Error ? error.message : '请确认后端已经启动。'); }
    finally { startLock.current = false; setStarting(false); }
  };

  const toggleSpeechRecognition = async () => {
    try {
      if (recognizing) {
        keepListeningRef.current = false;
        pendingAutoSubmitRef.current = true;
        if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
        ExpoSpeechRecognitionModule.stop();
        setSpeechStatus('正在结束录音并整理最后一段文字…');
        return;
      }
      if (!ExpoSpeechRecognitionModule.isRecognitionAvailable()) return showMessage('当前设备不支持语音识别', '你仍可直接输入文字完成面试。');
      const permission = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      if (!permission.granted) return showMessage('未获得语音权限', '你可以在系统设置中开启麦克风和语音识别权限，或直接输入文字。');
      const onDevice = ExpoSpeechRecognitionModule.supportsOnDeviceRecognition();
      setSpeechStatus(onDevice ? '将优先使用设备端中文识别。' : '此设备将使用系统提供的联网语音识别。');
      answerBeforeSpeechRef.current = answerRef.current; finalSpeechRef.current = ''; keepListeningRef.current = true; pendingAutoSubmitRef.current = false;
      startRecognizer();
    } catch (error) { showMessage('语音识别启动失败', error instanceof Error ? error.message : '当前问题仍然保留，请重试或直接输入文字。'); }
  };

  const downloadOfflineModel = async () => {
    try { await ExpoSpeechRecognitionModule.androidTriggerOfflineModelDownload({ locale: 'zh-CN' }); setSpeechStatus('系统已打开中文离线模型下载流程，完成后请重新尝试。'); }
    catch { showMessage('无法下载模型', '当前设备或语音服务不支持离线模型下载，可继续使用联网识别或文字输入。'); }
  };

  const pause = async () => {
    if (recognizing) { keepListeningRef.current = false; ExpoSpeechRecognitionModule.stop(); }
    const next = session.status === 'paused' ? 'active' : 'paused'; await setSessionStatus(next); track('interview_paused', { paused: next === 'paused', question_index: session.currentIndex });
  };

  const endEarly = () => confirmAction({ title: '提前结束面试？', message: session.answers.length ? '将根据已提交的回答生成简版报告，当前未提交内容不会计入。' : '尚未提交回答，结束后无法生成报告。', confirmText: '确认结束', cancelText: '继续面试', destructive: true, onConfirm: async () => { keepListeningRef.current = false; if (recognizing) ExpoSpeechRecognitionModule.abort(); if (session.answers.length) { await setSessionStatus('ended-early'); router.replace('/report'); } else { await clearSession(); router.replace('/'); } } });

  const submit = async () => {
    const submittedAnswer = answerRef.current.trim();
    pendingAutoSubmitRef.current = false;
    if (!submittedAnswer) { setSpeechStatus('没有识别到有效回答，请重新录音或输入文字。'); return showMessage('回答为空', '没有识别到有效语音，请重新回答或直接输入文字。'); }
    if (!state.resume || !session.interviewId || submittingRef.current) return;
    submittingRef.current = true; setSubmitting(true); await updateAnswerDraft(submittedAnswer);
    try {
      const result = await interviewGateway.turn(session, state.resume, submittedAnswer);
      keepListeningRef.current = false; ExpoSpeechRecognitionModule.abort();
      await applyInterviewTurn(submittedAnswer, result.next_question, result.completed); setDecisionNote(result.decision_reason); resetAnswerInput();
      track('question_answered', { question_index: session.currentIndex, follow_up: session.questions[session.currentIndex]?.is_follow_up ?? false });
      if (result.next_question?.is_follow_up) track('followup_triggered', { follow_up_count: result.next_question.follow_up_count });
      if (result.completed) { track('interview_completed', { answers: session.answers.length + 1, ended_early: false }); router.replace('/report'); }
    } catch (error) { showMessage('回答分析失败', `${error instanceof Error ? error.message : '请稍后重试。'}\n\n你的回答已保留，可以重新提交。`); }
    finally { submittingRef.current = false; setSubmitting(false); }
  };
  submitLatestRef.current = submit;

  const question = session.questions[session.currentIndex]; const paused = session.status === 'paused';
  return <Screen keyboard>
    <View style={styles.top}><View><Text style={styles.mode}>{session.mode === 'formal' ? '正式模拟' : '单项训练'}</Text><Text style={styles.role}>{session.target.title}</Text></View><View style={styles.controls}><Pressable onPress={pause}><Text style={styles.control}>{paused ? '继续' : '暂停'}</Text></Pressable><Pressable onPress={endEarly}><Text style={[styles.control, styles.end]}>结束</Text></Pressable></View></View>
    {question ? <View style={styles.progress}><View style={[styles.progressFill, { width: `${Math.min(100, ((question.main_question_index + 1) / Math.max(1, session.totalMainQuestions)) * 100)}%` }]} /></View> : null}
    {paused ? <Card tone="warning"><Text style={styles.pausedTitle}>面试已暂停</Text><Text style={styles.helper}>录音和流程已停止。点击右上角“继续”回到当前问题。</Text></Card> : <>
      <Card><Text style={styles.questionLabel}>{question ? `${question.stage} · 主问题 ${question.main_question_index + 1}/${session.totalMainQuestions}${question.is_follow_up ? ` · 追问 ${question.follow_up_count}/2` : ''}` : '准备开始'}</Text><Text style={styles.question}>{question?.text ?? 'AI 将根据已确认简历和目标岗位生成第一道问题。'}</Text>{question?.resume_evidence ? <View style={styles.evidenceBox}><Text style={styles.evidence}>本题依据：{question.resume_evidence}</Text></View> : null}{!question ? <Button label={starting ? '正在生成个性化问题…' : '开始面试'} disabled={starting} onPress={startInterview} /> : null}{starting ? <View style={styles.generating}><ActivityIndicator color={colors.primary} /><Text style={styles.helper}>通常需要数秒，请勿重复点击</Text></View> : null}</Card>
      <Card><Text style={styles.answerTitle}>你的回答</Text><Text style={styles.helper}>以语音回答为主。点击结束后会自动提交；文字仅用于实时查看、修正或备用输入。</Text>
        <Button label={recognizing ? '结束回答并自动提交' : answer ? '继续语音回答' : '开始语音回答'} disabled={submitting} variant={recognizing ? 'primary' : 'secondary'} onPress={toggleSpeechRecognition} />
        {speechStatus ? <Text style={styles.saved}>{speechStatus}</Text> : null}
        {Platform.OS === 'android' ? <Pressable onPress={downloadOfflineModel}><Text style={styles.modelLink}>下载中文离线识别模型（设备支持时）</Text></Pressable> : null}
        <TextInput value={answer} onChangeText={setCurrentAnswer} onBlur={() => updateAnswerDraft(answerRef.current)} multiline textAlignVertical="top" style={styles.textarea} placeholder="语音识别文字会显示在这里；需要时可以修正或直接输入" placeholderTextColor={colors.placeholder} />
        <Text style={styles.audioBoundary}>当前 Agent 根据语音识别出的回答内容判断，不对音色、语调或停顿作推测。</Text>
        {submitting ? <View style={styles.analyzing}><ActivityIndicator color={colors.primary} /><Text style={styles.helper}>{question?.follow_up_count === 2 ? '正在生成下一道主问题…' : '正在分析回答并准备下一题…'}</Text></View> : null}
        <View style={styles.actions}><Button label="保存文字草稿" variant="secondary" compact onPress={() => updateAnswerDraft(answerRef.current)} /><Button label={submitting ? '处理中…' : '提交文字回答'} disabled={submitting || recognizing || !question} compact onPress={submit} /></View>
      </Card>
    </>}
    {decisionNote ? <Card tone="blue"><Text style={styles.decision}>面试官判断：{decisionNote}</Text></Card> : null}
  </Screen>;
}

const styles = StyleSheet.create({
  title: { ...typography.title, color: colors.ink, marginTop: spacing.xl }, top: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: spacing.md }, mode: { color: colors.primary, fontWeight: '800', fontSize: 13 }, role: { ...typography.heading, color: colors.ink, marginTop: 3 }, controls: { flexDirection: 'row', gap: 16 }, control: { color: colors.primary, fontWeight: '800' }, end: { color: colors.danger }, progress: { height: 5, borderRadius: 3, backgroundColor: colors.border, overflow: 'hidden' }, progressFill: { height: '100%', backgroundColor: colors.primary },
  questionLabel: { color: colors.muted, fontSize: 13, fontWeight: '700' }, question: { ...typography.heading, color: colors.ink, marginVertical: spacing.lg }, evidenceBox: { backgroundColor: colors.primarySoft, borderRadius: radius.sm, padding: 10, marginBottom: spacing.md }, evidence: { color: colors.primary, fontSize: 12, lineHeight: 18 }, generating: { alignItems: 'center', marginTop: 12, gap: 6 },
  answerTitle: { ...typography.heading, color: colors.ink }, helper: { color: colors.muted, fontSize: 13, lineHeight: 19, marginVertical: 6 }, saved: { color: colors.success, fontSize: 12, lineHeight: 18, marginTop: 10 }, modelLink: { color: colors.primary, fontSize: 12, fontWeight: '700', marginTop: 10 }, textarea: { minHeight: 170, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: '#FAFAFA', padding: spacing.md, color: colors.ink, fontSize: 16, lineHeight: 24, marginTop: spacing.md }, audioBoundary: { color: colors.muted, fontSize: 11, lineHeight: 17, marginTop: spacing.sm }, analyzing: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: spacing.sm }, actions: { flexDirection: 'row', justifyContent: 'flex-end', gap: spacing.sm, marginTop: spacing.md }, decision: { color: colors.primary, lineHeight: 20 }, pausedTitle: { color: colors.warningText, fontWeight: '800', fontSize: 18 },
});
