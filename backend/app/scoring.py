from __future__ import annotations

from .schemas import DimensionScore

DIMENSIONS = ("内容完整性", "岗位匹配度", "表达逻辑", "流畅度", "个人贡献清晰度", "数据证据")
LEVEL_TO_SCORE = {1: 20, 2: 40, 3: 60, 4: 80, 5: 100}
LEVEL_ANCHORS = {
    1: "未展示该能力，或回答与问题明显无关",
    2: "仅有零散、模糊或主要依赖追问后才出现的证据",
    3: "提供基本可接受的相关证据，但深度、范围或清晰度有限",
    4: "提供清晰、具体且较完整的证据，能够说明行动与结果",
    5: "提供充分、具体且相互印证的证据，明显超过基本要求",
}


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
