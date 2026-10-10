from __future__ import annotations

from ..prompts.report import REPORT_ASSESSMENT_INSTRUCTIONS
from .runtime import RUNTIME_SKILLS, RuntimeSkill


RUNTIME_SKILLS.register(RuntimeSkill(
    name="generate_evidence_report",
    description="在最后一道主问题及必要追问完成后，根据本场真实问答和有效语音指标生成可追溯的六维证据型报告。",
    instructions=REPORT_ASSESSMENT_INSTRUCTIONS,
    tool_names=(
        "load_completed_interview",
        "load_delivery_metrics",
        "submit_report_assessment",
        "save_interview_report",
    ),
    supported_events=("interview_completed",),
    input_contract=(
        "程序确认当前回答分析为next_main，且remaining_main_questions为0",
        "本场至少包含一条已确认回答，每条回答具有真实question_id",
    ),
    output_contract=(
        "六个维度使用1–5级行为锚点或在证据不足时使用null",
        "每个已评分维度必须有理由、最多两个合法证据题目ID和可执行建议",
        "报告通过硬校验并完成保存尝试后才能结束Agent Run",
    ),
    fact_constraints=(
        "只能使用load_completed_interview和load_delivery_metrics返回的本场真实数据",
        "不得编造回答、证据、语音指标或百分制分数",
        "证据原文、完成题数、流畅度和总分由代码确定",
    ),
    failure_policy=(
        "面试未完成、证据ID非法、维度不完整或Schema错误时不保存报告",
        "提交校验失败时返回具体observation，最多允许一次定向纠正",
        "纠正后仍失败或超出模型调用预算时明确失败，不返回不可校验报告",
    ),
    acceptance_criteria=(
        "所有证据都可根据question_id回填到用户已确认回答原文",
        "每个维度都包含理由和可执行建议，证据不足时不强行评分",
        "报告不包含无关敏感属性，完成题数、分数和语音维度由代码复核",
    ),
))
