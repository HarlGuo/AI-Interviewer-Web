from __future__ import annotations

from .schemas import AnswerEvidence, DimensionScore

DIMENSIONS = ("内容完整性", "岗位匹配度", "表达逻辑", "流畅度", "个人贡献清晰度", "数据证据")
LEVEL_TO_SCORE = {1: 20, 2: 40, 3: 60, 4: 80, 5: 100}
LEVEL_ANCHORS = {
    1: "未展示该能力，或回答与问题明显无关",
    2: "仅有零散、模糊或主要依赖追问后才出现的证据",
    3: "提供基本可接受的相关证据，但深度、范围或清晰度有限",
    4: "提供清晰、具体且较完整的证据，能够说明行动与结果",
    5: "提供充分、具体且相互印证的证据，明显超过基本要求",
}


def _rate_level(rate: float) -> int:
    if 180 <= rate <= 320:
        return 5
    if 140 <= rate <= 380:
        return 4
    if 100 <= rate <= 440:
        return 3
    if 70 <= rate <= 500:
        return 2
    return 1


def _pause_level(ratio: float, longest_ms: int) -> int:
    if 0.08 <= ratio <= 0.35 and longest_ms <= 4_000:
        return 5
    if ratio <= 0.45 and longest_ms <= 6_000:
        return 4
    if ratio <= 0.55 and longest_ms <= 9_000:
        return 3
    if ratio <= 0.70 and longest_ms <= 15_000:
        return 2
    return 1


def build_delivery_dimension(answers: list[AnswerEvidence]) -> DimensionScore:
    measured = [item for item in answers if item.delivery_metrics and item.delivery_metrics.duration_ms >= 3_000]
    if not measured:
        return DimensionScore(
            name="流畅度", level=None, score=None,
            basis="本次回答未采集到足够的语音节奏数据，因此不对口语流畅度评分。",
            evidence=[], suggestion="下次使用语音回答并完整结束录音，即可获得语速和停顿反馈。",
        )
    total_duration = sum(item.delivery_metrics.duration_ms for item in measured if item.delivery_metrics)
    weighted_rate = round(sum(item.delivery_metrics.speech_rate_cpm * item.delivery_metrics.duration_ms for item in measured if item.delivery_metrics) / total_duration)
    total_pause = sum(item.delivery_metrics.average_pause_ms * item.delivery_metrics.pause_count for item in measured if item.delivery_metrics)
    pause_ratio = total_pause / total_duration if total_duration else 0
    longest_pause = max(item.delivery_metrics.longest_pause_ms for item in measured if item.delivery_metrics)
    volume_variation = sum(item.delivery_metrics.volume_variation for item in measured if item.delivery_metrics) / len(measured)
    level = round((_rate_level(weighted_rate) + _pause_level(pause_ratio, longest_pause)) / 2)
    pause_percent = round(pause_ratio * 100)
    return DimensionScore(
        name="流畅度", level=level, score=None,
        basis=f"语音实测：平均语速约 {weighted_rate} 字/分钟，停顿约占 {pause_percent}%，最长停顿 {longest_pause / 1000:.1f} 秒；音量波动 {volume_variation:.1f} 仅用于判断收音稳定性。",
        evidence=[measured[0].answer.strip()[:280]],
        suggestion="保持自然语速；在观点切换处短暂停顿，避免长时间停顿或连续过快表达。",
    )


def replace_delivery_dimension(dimensions: list[DimensionScore], answers: list[AnswerEvidence]) -> list[DimensionScore]:
    delivery = build_delivery_dimension(answers)
    return [delivery if item.name == "流畅度" else item for item in dimensions]


def finalize_dimensions(dimensions: list[DimensionScore], answer_text: str) -> tuple[list[DimensionScore], int]:
    by_name = {item.name: item for item in dimensions}
    if set(by_name) != set(DIMENSIONS) or len(dimensions) != len(DIMENSIONS):
        raise ValueError("报告必须且只能包含规定的六个评分维度")
    finalized: list[DimensionScore] = []
    scores: list[int] = []
    for name in DIMENSIONS:
        item = by_name[name]
        if any(evidence not in answer_text for evidence in item.evidence):
            finalized.append(item.model_copy(update={"level": None, "score": None, "basis": "证据不足：模型返回的证据无法在已确认回答中逐字核对。", "evidence": []}))
            continue
        if item.level is None or not item.evidence:
            finalized.append(item.model_copy(update={"level": None, "score": None, "basis": "证据不足"}))
            continue
        score = LEVEL_TO_SCORE[item.level]
        scores.append(score)
        finalized.append(item.model_copy(update={"score": score}))
    return finalized, round(sum(scores) / len(scores)) if scores else 0
