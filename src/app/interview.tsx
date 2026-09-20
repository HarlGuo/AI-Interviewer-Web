import { ExpoSpeechRecognitionModule, useSpeechRecognitionEvent } from 'expo-speech-recognition';
import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { Button, Card, Screen } from '@/components/ui';
import { InterviewFeedbackModal } from '@/components/interview-feedback-modal';
import { FeedbackSubmission } from '@/domain/models';
import { createUuid } from '@/services/ids';
import { ApiNotConfiguredError, interviewGateway } from '@/services/gateways';
import { confirmAction, showMessage } from '@/services/dialogs';
import { track } from '@/services/telemetry';
import { SpeechDeliveryTracker } from '@/services/speech-delivery';
import { cleanUserFacingText } from '@/services/user-facing-text';
import { useApp } from '@/state/app-context';
import { colors, radius, spacing, typography } from '@/theme/tokens';

export default function InterviewScreen() {
  const { state, hydrated, activateSession, ensureInterviewId, updateAnswerDraft, applyInterviewTurn, setSessionStatus, clearSession } = useApp();
  const session = state.activeSession;
  const [answer, setAnswer] = useState(session?.answerDraft ?? ''); const [starting, setStarting] = useState(false); const [submitting, setSubmitting] = useState(false); const [recognizing, setRecognizing] = useState(false); const [speechStatus, setSpeechStatus] = useState(''); const startLock = useRef(false);
  const [feedbackType, setFeedbackType] = useState<'completed' | 'ended_early' | null>(null); const [feedbackSubmitting, setFeedbackSubmitting] = useState(false); const [feedbackError, setFeedbackError] = useState(''); const [finishWithoutReport, setFinishWithoutReport] = useState(false);
  const currentQuestionId = session?.questions[session.currentIndex]?.id ?? null;
  const keepListeningRef = useRef(false); const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null); const autoSubmitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null); const draftTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null); const answerBeforeSpeechRef = useRef(''); const finalSpeechRef = useRef(''); const answerRef = useRef(session?.answerDraft ?? ''); const pendingAutoSubmitRef = useRef(false); const submittingRef = useRef(false); const submitLatestRef = useRef<() => Promise<void>>(async () => undefined); const updateAnswerDraftRef = useRef(updateAnswerDraft); const previousQuestionIdRef = useRef(currentQuestionId); const speechUsedRef = useRef(false); const recordingStartedAtRef = useRef<number | null>(null); const presentedQuestionRef = useRef<string | null>(null); const deliveryTrackerRef = useRef(new SpeechDeliveryTracker()); const deliveryMetricsRef = useRef<ReturnType<SpeechDeliveryTracker['finish']>>(null);

  const joinTranscript = (base: string, speech: string) => [base.trim(), speech.trim()].filter(Boolean).join(base.trim() && speech.trim() ? '\n' : '');
  updateAnswerDraftRef.current = updateAnswerDraft;
  const persistDraft = () => { if (draftTimerRef.current) clearTimeout(draftTimerRef.current); draftTimerRef.current = null; void updateAnswerDraftRef.current(answerRef.current); };
  const setCurrentAnswer = (text: string) => {
    answerRef.current = text; setAnswer(text);
    if (draftTimerRef.current) clearTimeout(draftTimerRef.current);
    draftTimerRef.current = setTimeout(persistDraft, 500);
  };
  const resetAnswerInput = () => {
    answerBeforeSpeechRef.current = ''; finalSpeechRef.current = ''; answerRef.current = '';
    pendingAutoSubmitRef.current = false; deliveryMetricsRef.current = null; setAnswer(''); setSpeechStatus('');
  };
  const restoreAnswerInput = (text: string) => {
    answerBeforeSpeechRef.current = ''; finalSpeechRef.current = ''; answerRef.current = text;
    pendingAutoSubmitRef.current = false; deliveryMetricsRef.current = null; setAnswer(text);
    setSpeechStatus(text ? '已恢复上次未提交的回答。' : '');
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
      volumeChangeEventOptions: { enabled: true, intervalMillis: 100 },
    });
  };

  useSpeechRecognitionEvent('volumechange', (event) => deliveryTrackerRef.current.addVolume(event.value));

  useSpeechRecognitionEvent('start', () => { setRecognizing(true); if (!recordingStartedAtRef.current) { recordingStartedAtRef.current = Date.now(); track('recording_started', { input_mode: 'speech_transcript' }, session?.interviewId); } setSpeechStatus('正在聆听，请自然作答；短暂停顿不会结束本题。'); });
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
    if (speechUsedRef.current) deliveryMetricsRef.current = deliveryTrackerRef.current.finish(answerRef.current);
    persistDraft();
    if (recordingStartedAtRef.current) { const seconds = Math.round((Date.now() - recordingStartedAtRef.current) / 1000); track('recording_stopped', { recording_duration_bucket: seconds < 60 ? '<1m' : seconds < 180 ? '1-3m' : '3m+' }, session?.interviewId); recordingStartedAtRef.current = null; }
    if (pendingAutoSubmitRef.current) {
      setSpeechStatus('录音回答已结束，正在提交给面试官…');
      autoSubmitTimerRef.current = setTimeout(() => void submitLatestRef.current(), 300);
    } else setSpeechStatus((current) => current || '语音输入已结束，文字仍可编辑。');
  });
  useSpeechRecognitionEvent('result', (event) => {
    if (submittingRef.current) return;
    const transcript = event.results[0]?.transcript?.trim();
    if (!transcript) return;
    speechUsedRef.current = true; if (event.isFinal) { finalSpeechRef.current = joinTranscript(finalSpeechRef.current, transcript); track('transcription_succeeded', { character_bucket: transcript.length < 100 ? '<100' : transcript.length < 500 ? '100-499' : '500+' }, session?.interviewId); }
    setCurrentAnswer(joinTranscript(answerBeforeSpeechRef.current, event.isFinal ? finalSpeechRef.current : joinTranscript(finalSpeechRef.current, transcript)));
    setSpeechStatus(event.isFinal ? '已记录这一段，仍在继续聆听…' : '正在生成转写文字…');
  });
  useSpeechRecognitionEvent('error', (event) => {
    if (keepListeningRef.current && (event.error === 'no-speech' || event.error === 'speech-timeout')) {
      setSpeechStatus('暂时没有识别到语音，仍在继续聆听…'); return;
    }
    keepListeningRef.current = false; setRecognizing(false);
    deliveryMetricsRef.current = deliveryTrackerRef.current.finish(answerRef.current);
    persistDraft();
    if (event.error === 'aborted') return;
    const messages: Partial<Record<typeof event.error, string>> = {
      'not-allowed': '未获得麦克风或语音识别权限，可在系统设置中开启，或直接输入文字。',
      'no-speech': '没有识别到语音，请靠近麦克风重试，或直接输入文字。',
      'speech-timeout': '等待语音超时，请重新开始语音输入。',
      'language-not-supported': '设备尚未提供中文识别模型，可下载离线模型或直接输入文字。',
      network: '系统语音识别网络连接失败，回答文字仍会保留。',
      'service-not-allowed': '此设备当前无法使用系统语音识别，请直接输入文字。',
    };
    track('transcription_failed', { error_code: event.error }, session?.interviewId);
    const message = messages[event.error] ?? `语音识别失败：${event.message || event.error}`;
    setSpeechStatus(message); showMessage('转写未完成', message);
  });
  useEffect(() => () => {
    keepListeningRef.current = false;
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    if (autoSubmitTimerRef.current) clearTimeout(autoSubmitTimerRef.current);
    persistDraft();
    ExpoSpeechRecognitionModule.abort();
  }, []);
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return;
    const saveBeforeBackground = () => {
      if (document.visibilityState !== 'hidden') return;
      persistDraft();
      if (keepListeningRef.current) {
        keepListeningRef.current = false;
        pendingAutoSubmitRef.current = false;
        ExpoSpeechRecognitionModule.stop();
        setSpeechStatus('语音已暂停，已识别内容会保留。');
      }
    };
    const saveBeforeUnload = () => persistDraft();
    document.addEventListener('visibilitychange', saveBeforeBackground);
    window.addEventListener('pagehide', saveBeforeUnload);
    return () => {
      document.removeEventListener('visibilitychange', saveBeforeBackground);
      window.removeEventListener('pagehide', saveBeforeUnload);
    };
  }, []);
  useEffect(() => {
    if (previousQuestionIdRef.current === currentQuestionId) return;
    previousQuestionIdRef.current = currentQuestionId;
    keepListeningRef.current = false;
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    if (autoSubmitTimerRef.current) clearTimeout(autoSubmitTimerRef.current);
    if (draftTimerRef.current) clearTimeout(draftTimerRef.current);
    ExpoSpeechRecognitionModule.abort();
    restoreAnswerInput(session?.answerDraft ?? '');
  }, [currentQuestionId, session?.id]);
  useEffect(() => {
    if (!currentQuestionId || presentedQuestionRef.current === currentQuestionId || !session) return;
    presentedQuestionRef.current = currentQuestionId;
    const current = session.questions[session.currentIndex];
    track('question_presented', { stage: current.stage, main_question_index: current.main_question_index, is_follow_up: current.is_follow_up }, session.interviewId);
  }, [currentQuestionId, session]);
  if (!hydrated) return <Screen><View style={styles.loading}><ActivityIndicator color={colors.primary} /><Text style={styles.helper}>正在恢复面试…</Text></View></Screen>;
  if (!session) return <Screen><Text style={styles.title}>没有可恢复的面试</Text><Button label="返回首页" onPress={() => router.replace('/')} /></Screen>;

  const startInterview = async () => {
    if (startLock.current) return; startLock.current = true; setStarting(true);
    const interviewId = session.interviewId || createUuid();
    if (!session.interviewId) await ensureInterviewId(interviewId);
    const startedAt = Date.now(); track('interview_start_requested', { mode: session.mode, focus: session.focus }, interviewId);
    try {
      if (!state.resume || state.resume.reviewStatus !== 'ai_verified' || state.resume.status !== 'confirmed') throw new Error('请先完成简历解析、AI 复核和用户确认。');
      const result = await interviewGateway.start({ ...session, interviewId }, state.resume); await activateSession(result.interview_id, result.question, result.total_main_questions); track('interview_started', { question_source: result.source, mode: session.mode, latency_ms: Date.now() - startedAt }, result.interview_id);
    } catch (error) { track('interview_start_failed', { error_code: error instanceof ApiNotConfiguredError ? 'not_configured' : 'request_failed', latency_ms: Date.now() - startedAt }, interviewId); showMessage(error instanceof ApiNotConfiguredError ? '后端地址尚未配置' : '面试启动失败', error instanceof Error ? error.message : '请确认后端已经启动。'); }
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
      setSpeechStatus('语音输入已准备好。');
      answerBeforeSpeechRef.current = answerRef.current; finalSpeechRef.current = ''; keepListeningRef.current = true; pendingAutoSubmitRef.current = false; speechUsedRef.current = true; deliveryMetricsRef.current = null; deliveryTrackerRef.current.start();
      startRecognizer();
    } catch (error) { showMessage('语音识别启动失败', error instanceof Error ? error.message : '当前问题仍然保留，请重试或直接输入文字。'); }
  };

  const downloadOfflineModel = async () => {
    try { await ExpoSpeechRecognitionModule.androidTriggerOfflineModelDownload({ locale: 'zh-CN' }); setSpeechStatus('系统已打开中文离线模型下载流程，完成后请重新尝试。'); }
    catch { showMessage('无法下载模型', '当前设备或语音服务不支持离线模型下载，可继续使用联网识别或文字输入。'); }
  };

  const pause = async () => {
    if (recognizing) { keepListeningRef.current = false; ExpoSpeechRecognitionModule.stop(); }
    const next = session.status === 'paused' ? 'active' : 'paused'; await setSessionStatus(next); if (session.interviewId) await interviewGateway.updateStatus(session.interviewId, next).catch(() => undefined); track(next === 'paused' ? 'interview_paused' : 'interview_resumed', { question_index: session.currentIndex }, session.interviewId);
  };

  const showFeedback = (type: 'completed' | 'ended_early', withoutReport = false) => { setFinishWithoutReport(withoutReport); setFeedbackType(type); track('feedback_prompt_viewed', { completion_type: type }, session.interviewId); };
  const finishAfterFeedback = async () => { setFeedbackType(null); if (finishWithoutReport) { await clearSession(); router.replace('/'); } else router.replace('/report'); };
  const submitFeedback = async (feedback: FeedbackSubmission) => { if (!session.interviewId) return finishAfterFeedback(); setFeedbackSubmitting(true); setFeedbackError(''); try { await interviewGateway.feedback(session.interviewId, feedback); track('feedback_submitted', { satisfaction_score: feedback.satisfaction_score, payment_willingness: feedback.payment_willingness, tags: feedback.tags, completion_type: feedback.completion_type }, session.interviewId); await finishAfterFeedback(); } catch { setFeedbackError('反馈暂时未保存，你可以重试或选择“暂不反馈”。'); } finally { setFeedbackSubmitting(false); } };
  const skipFeedback = () => { track('feedback_skipped', { completion_type: feedbackType }, session.interviewId); void finishAfterFeedback(); };
  const endEarly = () => confirmAction({ title: '提前结束面试？', message: session.answers.length ? '将根据已提交的回答生成简版报告，当前未提交内容不会计入。' : '尚未提交回答，结束后无法生成报告。', confirmText: '确认结束', cancelText: '继续面试', destructive: true, onConfirm: async () => { keepListeningRef.current = false; if (recognizing) ExpoSpeechRecognitionModule.abort(); if (session.interviewId) await interviewGateway.updateStatus(session.interviewId, 'ended-early').catch(() => undefined); await setSessionStatus('ended-early'); track('interview_ended_early', { answered_count: session.answers.length, last_stage: session.questions[session.currentIndex]?.stage ?? null }, session.interviewId); showFeedback('ended_early', session.answers.length === 0); } });

  const submit = async () => {
    const submittedAnswer = answerRef.current.trim();
    pendingAutoSubmitRef.current = false;
    if (!submittedAnswer) { setSpeechStatus('没有识别到有效回答，请重新录音或输入文字。'); return showMessage('回答为空', '没有识别到有效语音，请重新回答或直接输入文字。'); }
    if (!state.resume || !session.interviewId || submittingRef.current) return;
    const source = speechUsedRef.current ? 'speech_transcript' : 'text'; const submittedAt = Date.now();
    submittingRef.current = true; setSubmitting(true); await updateAnswerDraft(submittedAnswer); track('answer_submit_requested', { question_index: session.currentIndex, input_mode: source }, session.interviewId);
    try {
      const deliveryMetrics = source === 'speech_transcript' ? deliveryMetricsRef.current : null;
      const result = await interviewGateway.turn(session, state.resume, submittedAnswer, source, deliveryMetrics);
      keepListeningRef.current = false; ExpoSpeechRecognitionModule.abort();
      await applyInterviewTurn(submittedAnswer, source, deliveryMetrics, result.next_question, result.completed); resetAnswerInput(); speechUsedRef.current = false;
      track('answer_accepted', { question_index: session.currentIndex, is_follow_up: session.questions[session.currentIndex]?.is_follow_up ?? false, input_mode: source, latency_ms: Date.now() - submittedAt }, session.interviewId);
      if (result.next_question?.is_follow_up) track('followup_triggered', { follow_up_count: result.next_question.follow_up_count }, session.interviewId);
      if (result.completed) { track('interview_completed', { answered_count: session.answers.length + 1, completion_type: 'completed' }, session.interviewId); showFeedback('completed'); }
    } catch (error) { track('answer_failed', { question_index: session.currentIndex, input_mode: source, error_code: 'request_failed', latency_ms: Date.now() - submittedAt }, session.interviewId); showMessage('回答分析失败', `${error instanceof Error ? error.message : '请稍后重试。'}\n\n你的回答已保留，可以重新提交。`); }
    finally { submittingRef.current = false; setSubmitting(false); }
  };
  submitLatestRef.current = submit;

  const question = session.questions[session.currentIndex]; const paused = session.status === 'paused';
  return <><Screen keyboard>
    <View style={styles.top}><View><Text style={styles.mode}>{session.mode === 'formal' ? '正式模拟' : '单项训练'}</Text><Text style={styles.role}>{session.target.title}</Text></View><View style={styles.controls}><Pressable onPress={pause}><Text style={styles.control}>{paused ? '继续' : '暂停'}</Text></Pressable><Pressable onPress={endEarly}><Text style={[styles.control, styles.end]}>结束</Text></Pressable></View></View>
    {question ? <View style={styles.progress}><View style={[styles.progressFill, { width: `${Math.min(100, ((question.main_question_index + 1) / Math.max(1, session.totalMainQuestions)) * 100)}%` }]} /></View> : null}
    {paused ? <Card tone="warning"><Text style={styles.pausedTitle}>面试已暂停</Text><Text style={styles.helper}>录音和流程已停止。点击右上角“继续”回到当前问题。</Text></Card> : <>
      <Card><Text style={styles.questionLabel}>{question ? `${question.stage} · 主问题 ${question.main_question_index + 1}/${session.totalMainQuestions}${question.is_follow_up ? ` · 追问 ${question.follow_up_count}/2` : ''}` : '准备开始'}</Text><Text style={styles.question}>{question ? cleanUserFacingText(question.text) : '将根据已确认简历和目标岗位生成第一道问题。'}</Text>{question?.resume_evidence && cleanUserFacingText(question.resume_evidence) ? <View style={styles.evidenceBox}><Text style={styles.evidence}>相关经历：{cleanUserFacingText(question.resume_evidence)}</Text></View> : null}{!question ? <Button label={starting ? '正在启动面试…' : '开始面试'} disabled={starting} onPress={startInterview} /> : null}{starting ? <View style={styles.generating}><ActivityIndicator color={colors.primary} /><Text style={styles.helper}>第一题为固定开场，请保持此页；网络超时后可再次点击，不会重复占用今日次数。</Text></View> : null}</Card>
      <Card><Text style={styles.answerTitle}>你的回答</Text><Text style={styles.helper}>以语音回答为主。点击结束后会自动提交；文字仅用于实时查看、修正或备用输入。</Text>
        <Button label={recognizing ? '结束回答并自动提交' : answer ? '继续语音回答' : '开始语音回答'} disabled={submitting} variant={recognizing ? 'primary' : 'secondary'} onPress={toggleSpeechRecognition} />
        {speechStatus ? <Text style={styles.saved}>{speechStatus}</Text> : null}
        {Platform.OS === 'android' ? <Pressable onPress={downloadOfflineModel}><Text style={styles.modelLink}>下载中文离线识别模型（设备支持时）</Text></Pressable> : null}
        <TextInput value={answer} onChangeText={setCurrentAnswer} onBlur={() => updateAnswerDraft(answerRef.current)} multiline textAlignVertical="top" style={styles.textarea} placeholder="语音识别文字会显示在这里；需要时可以修正或直接输入" placeholderTextColor={colors.placeholder} />
        {submitting ? <View style={styles.analyzing}><ActivityIndicator color={colors.primary} /><Text style={styles.helper}>{question?.follow_up_count === 2 ? '正在生成下一道主问题…' : '正在分析回答并准备下一题…'}</Text></View> : null}
        <View style={styles.actions}><Button label="保存文字草稿" variant="secondary" compact onPress={() => updateAnswerDraft(answerRef.current)} /><Button label={submitting ? '处理中…' : '提交文字回答'} disabled={submitting || recognizing || !question} compact onPress={submit} /></View>
      </Card>
    </>}
  </Screen><InterviewFeedbackModal visible={feedbackType !== null} completionType={feedbackType ?? 'ended_early'} submitting={feedbackSubmitting} error={feedbackError} onSubmit={submitFeedback} onSkip={skipFeedback} /></>;
}

const styles = StyleSheet.create({
  title: { ...typography.title, color: colors.ink, marginTop: spacing.xl }, loading: { minHeight: 240, alignItems: 'center', justifyContent: 'center' }, top: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: spacing.md }, mode: { color: colors.primary, fontWeight: '800', fontSize: 13 }, role: { ...typography.heading, color: colors.ink, marginTop: 3 }, controls: { flexDirection: 'row', gap: 16 }, control: { color: colors.primary, fontWeight: '800' }, end: { color: colors.danger }, progress: { height: 5, borderRadius: 3, backgroundColor: colors.border, overflow: 'hidden' }, progressFill: { height: '100%', backgroundColor: colors.primary },
  questionLabel: { color: colors.muted, fontSize: 13, fontWeight: '700' }, question: { ...typography.heading, color: colors.ink, marginVertical: spacing.lg }, evidenceBox: { backgroundColor: colors.primarySoft, borderRadius: radius.sm, padding: 10, marginBottom: spacing.md }, evidence: { color: colors.primary, fontSize: 12, lineHeight: 18 }, generating: { alignItems: 'center', marginTop: 12, gap: 6 },
  answerTitle: { ...typography.heading, color: colors.ink }, helper: { color: colors.muted, fontSize: 13, lineHeight: 19, marginVertical: 6 }, saved: { color: colors.success, fontSize: 12, lineHeight: 18, marginTop: 10 }, modelLink: { color: colors.primary, fontSize: 12, fontWeight: '700', marginTop: 10 }, textarea: { minHeight: 170, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: '#FAFAFA', padding: spacing.md, color: colors.ink, fontSize: 16, lineHeight: 24, marginTop: spacing.md }, analyzing: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: spacing.sm }, actions: { flexDirection: 'row', justifyContent: 'flex-end', gap: spacing.sm, marginTop: spacing.md }, pausedTitle: { color: colors.warningText, fontWeight: '800', fontSize: 18 },
});
