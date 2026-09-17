import { SpeechDeliveryMetrics } from '@/domain/models';

const SAMPLE_INTERVAL_MS = 100;
const AUDIBLE_THRESHOLD = 0;
const MIN_PAUSE_MS = 600;

type VolumeSample = { at: number; value: number };

function countSpokenCharacters(transcript: string) {
  return (transcript.match(/[\p{L}\p{N}]/gu) ?? []).length;
}

export class SpeechDeliveryTracker {
  private startedAt: number | null = null;
  private samples: VolumeSample[] = [];

  start(at = Date.now()) {
    this.startedAt = at;
    this.samples = [];
  }

  addVolume(value: number, at = Date.now()) {
    if (this.startedAt === null || !Number.isFinite(value)) return;
    this.samples.push({ at, value });
  }

  finish(transcript: string, endedAt = Date.now()): SpeechDeliveryMetrics | null {
    if (this.startedAt === null) return null;
    const startedAt = this.startedAt;
    this.startedAt = null;
    const samples = this.samples;
    this.samples = [];
    const durationMs = Math.max(0, endedAt - startedAt);
    if (durationMs < 3_000 || samples.length < 10) return null;

    let voicedDurationMs = 0;
    let silenceStartedAt: number | null = null;
    let hasVoiced = false;
    const pauses: number[] = [];
    const voicedVolumes: number[] = [];

    samples.forEach((sample, index) => {
      const nextAt = samples[index + 1]?.at ?? endedAt;
      const interval = Math.max(0, Math.min(500, nextAt - sample.at || SAMPLE_INTERVAL_MS));
      if (sample.value >= AUDIBLE_THRESHOLD) {
        voicedDurationMs += interval;
        voicedVolumes.push(sample.value);
        if (silenceStartedAt !== null && hasVoiced) {
          const pause = sample.at - silenceStartedAt;
          if (pause >= MIN_PAUSE_MS) pauses.push(pause);
        }
        silenceStartedAt = null;
        hasVoiced = true;
      } else if (hasVoiced && silenceStartedAt === null) {
        silenceStartedAt = sample.at;
      }
    });

    if (voicedDurationMs < 1_000 || voicedVolumes.length < 5) return null;
    const characterCount = countSpokenCharacters(transcript);
    const averageVolume = voicedVolumes.reduce((sum, value) => sum + value, 0) / voicedVolumes.length;
    const variance = voicedVolumes.reduce((sum, value) => sum + ((value - averageVolume) ** 2), 0) / voicedVolumes.length;

    return {
      duration_ms: Math.round(durationMs),
      voiced_duration_ms: Math.round(voicedDurationMs),
      pause_count: pauses.length,
      average_pause_ms: pauses.length ? Math.round(pauses.reduce((sum, value) => sum + value, 0) / pauses.length) : 0,
      longest_pause_ms: pauses.length ? Math.round(Math.max(...pauses)) : 0,
      speech_rate_cpm: durationMs > 0 ? Math.round(characterCount * 60_000 / durationMs) : 0,
      average_volume: Number(averageVolume.toFixed(2)),
      volume_variation: Number(Math.sqrt(variance).toFixed(2)),
      sample_count: samples.length,
    };
  }
}
