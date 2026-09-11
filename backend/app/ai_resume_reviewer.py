from __future__ import annotations

import json
import re
from collections import Counter

from pydantic import BaseModel

from .config import settings
from .deepseek_client import chat_json
from .schemas import ResumeParseResponse, ResumeSection

ALLOWED_SECTIONS = ("基本信息", "个人总结", "教育经历", "工作/实习经历", "项目经历", "技能/证书及其他", "其他")
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")

SYSTEM_PROMPT = """你是简历文本结构复核器。必须输出 JSON，不能改写、补充或删除任何原文事实。
你只需要把每个 line_id 分类到一个 section。section 只能是：基本信息、个人总结、教育经历、工作/实习经历、项目经历、技能/证书及其他、其他。
每个输入 line_id 必须且只能出现一次。不要输出原文内容，不要推断被脱敏的信息。
JSON 格式：{"assignments":[{"line_id":"L001","section":"基本信息"}],"issues":["可选的解析风险说明"]}。"""


class Assignment(BaseModel):
    line_id: str
    section: str


class ReviewPayload(BaseModel):
    assignments: list[Assignment]
    issues: list[str]


def _redact(text: str) -> str:
    return PHONE_PATTERN.sub("[PHONE_REDACTED]", EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text))


async def review_resume(parsed: ResumeParseResponse) -> ResumeParseResponse:
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    originals: list[tuple[str, str]] = []
    for section in parsed.sections:
        for line in section.content.splitlines():
            if line.strip():
                originals.append((f"L{len(originals) + 1:03d}", line.strip()))
    if not originals:
        raise ValueError("没有可供 AI 复核的简历文本")

    review_input = [{"line_id": line_id, "text": _redact(text)} for line_id, text in originals]
    response = await _call_deepseek(review_input)
    expected = {line_id for line_id, _ in originals}
    returned = [item.line_id for item in response.assignments]
    counts = Counter(returned)
    if set(returned) != expected or any(count != 1 for count in counts.values()):
        raise ValueError("AI 复核结果存在行遗漏、重复或未知行")
    if any(item.section not in ALLOWED_SECTIONS for item in response.assignments):
        raise ValueError("AI 复核返回了不允许的区块")

    assignment_by_id = {item.line_id: item.section for item in response.assignments}
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for line_id, original_text in originals:
        section = assignment_by_id[line_id]
        if section not in grouped:
            grouped[section] = []
            order.append(section)
        grouped[section].append(original_text)

    return parsed.model_copy(update={
        "sections": [ResumeSection(title=title, content="\n".join(grouped[title])) for title in order],
        "review_status": "ai_verified",
        "review_issues": response.issues,
        "warnings": parsed.warnings + ["AI 已完成行级分类复核；所有原文行均通过完整性校验，仍需用户最终确认。"],
    })


async def _call_deepseek(lines: list[dict[str, str]]) -> ReviewPayload:
    content = await chat_json(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "请复核以下 JSON lines：\n" + json.dumps(lines, ensure_ascii=False)},
        ],
        temperature=0,
        max_tokens=4000,
        purpose="resume review",
    )
    return ReviewPayload.model_validate(content)
